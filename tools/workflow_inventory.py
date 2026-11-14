"""Read-only inventory of Deplao workflow JSON. Never deletes, moves or prints secrets.

Compares each graph, after redacting credentials/IDs/paths, with the canonical
graphs from tools/build_deplao_workflows.py (built from dummy values) and
classifies it: current-*, legacy-*, duplicate, runtime-config or unknown.

    .\\.venv\\Scripts\\python.exe -m tools.workflow_inventory
    .\\.venv\\Scripts\\python.exe -m tools.workflow_inventory --git-ref origin/main

A file on disk says nothing about what is imported/enabled inside Deplao.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from tools.build_deplao_workflows import build_image_intake, build_intake, build_publisher

ROOT = Path(__file__).resolve().parents[1]
SECRET_KEYS = re.compile(r'key|token|secret|password|cookie|authorization|session', re.I)
SECRET_HEADERS = ('X-API-Key', 'X-Intake-Key', 'Authorization')
NOT_WORKFLOWS = {'local-config.json': 'runtime-config', 'zalo-channel.json': 'runtime-config'}
KEEP_SUFFIXES = ('.db', '.db-wal', '.db-shm', '.sqlite', '.dpapi', '.bin', '.key')


def redact(value, key=''):
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items() if k != 'position'}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    if not isinstance(value, str):
        return value
    if key == 'headers':
        try:
            headers = json.loads(value)
            return {k: ('<SECRET>' if k in SECRET_HEADERS else v) for k, v in sorted(headers.items())}
        except (ValueError, AttributeError):
            return '<HEADERS>'
    if SECRET_KEYS.search(key) and value:
        return '<SECRET>'
    value = re.sub(r'YOUR_[A-Z_]+', '<PLACEHOLDER>', value)
    value = re.sub(r'(?<![0-9a-f])[0-9]{6,}(?![0-9a-f])', '<ID>', value)
    value = re.sub(r'\^?(?:[A-Za-z]:\\\\?|/)[^"\s]*group-media[^"\s]*', '<MEDIA_PATH>', value)
    return value


def shape(graph: dict) -> dict:
    labels = {n['id']: n['label'] for n in graph.get('nodes', [])}
    return {'nodes': sorted((n['type'], n['label']) for n in graph.get('nodes', [])),
            'edges': sorted((labels.get(e['source'], e['source']), labels.get(e['target'], e['target']),
                             e.get('sourceHandle', 'default')) for e in graph.get('edges', []))}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def canonical() -> dict[str, dict]:
    key, account, other = 'inventory-dummy-key-0000000000', '100000000001', '100000000002'
    graphs = {
        'current-text-intake': build_intake(key, account, other, binding_verified=True),
        'current-image-intake': build_image_intake(key, account, other, binding_verified=True,
                                                   image_metadata_verified=True),
        'current-publisher-v2': build_publisher(key, account, other, policy_validated=True,
                                                binding_verified=True, version=2),
        'superseded-publisher-v1': build_publisher(key, account, other, policy_validated=True,
                                                   binding_verified=True, version=1),
    }
    return {name: {'shape': digest(shape(g)), 'full': digest(redact(g))} for name, g in graphs.items()}


def classify(graph: dict, references: dict) -> tuple[str, str]:
    fingerprint = digest(shape(graph))
    for name, ref in references.items():
        if fingerprint == ref['shape']:
            same = digest(redact(graph)) == ref['full']
            return name, 'matches generator' if same else 'same graph shape, config differs (review before use)'
    types = {n['type'] for n in graph.get('nodes', [])}
    text = json.dumps(graph, ensure_ascii=False)
    if 'ai.generateText' in types and 'trigger.message' in types:
        return 'legacy-standalone-pm-responder', 'answers PMs itself; competes with backend intake'
    if '/deliveries/claim' in text or 'zalo.sendImage' in types:
        return 'legacy-publisher', 'claims/sends group posts; competes with publisher v2'
    if 'trigger.message' in types and ('/events' in text or '/intake' in text or 'httpRequest' in text):
        return 'legacy-intake', 'forwards PMs; competes with current text/image intake'
    return 'unknown', 'not recognised; keep and inspect manually'


def load_sources(paths: list[Path], git_ref: str | None):
    for path in paths:
        files = sorted(p for p in path.rglob('*') if p.is_file()) if path.is_dir() else [path] if path.exists() else []
        for file in files:
            yield str(file.relative_to(ROOT) if file.is_relative_to(ROOT) else file), file, None
    if git_ref:
        listed = subprocess.run(['git', 'ls-tree', '-r', '--name-only', git_ref, '--', 'workflows', 'private'],
                                cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        for name in listed:
            blob = subprocess.run(['git', 'show', f'{git_ref}:{name}'], cwd=ROOT, capture_output=True, check=True).stdout
            yield f'{git_ref}:{name}', None, blob


def inventory(paths: list[Path], git_ref: str | None = None) -> list[dict]:
    references, rows, seen = canonical(), [], {}
    for name, file, blob in load_sources(paths, git_ref):
        base = name.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
        if base in NOT_WORKFLOWS or base.endswith(KEEP_SUFFIXES) or not base.endswith('.json'):
            rows.append({'source': name, 'class': NOT_WORKFLOWS.get(base, 'private-data' if base.endswith(KEEP_SUFFIXES) else 'non-workflow'),
                         'note': 'keep; not parsed or printed', 'fingerprint': '-'})
            continue
        try:
            graph = json.loads(blob.decode('utf-8-sig') if blob is not None else file.read_text(encoding='utf-8-sig'))
            if graph.get('_deplaoWorkflow') is not True:
                raise ValueError
        except (ValueError, UnicodeError, AttributeError):
            rows.append({'source': name, 'class': 'unknown', 'note': 'not a Deplao export; keep', 'fingerprint': '-'})
            continue
        kind, note = classify(graph, references)
        full = digest(redact(graph))
        if full in seen:
            kind, note = 'duplicate', f'same redacted graph as {seen[full]}'
        seen.setdefault(full, name)
        rows.append({'source': name, 'class': kind, 'note': note, 'fingerprint': full,
                     'name': redact(graph.get('name', ''))})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paths', nargs='*', type=Path, default=[ROOT / 'workflows', ROOT / 'private'])
    parser.add_argument('--git-ref', help='also inspect tracked workflows/ and private/ at this ref (read-only)')
    args = parser.parse_args()
    rows = inventory([p.resolve() for p in args.paths], args.git_ref)
    for row in rows:
        print(f"{row['class']:32} {row['fingerprint']:16} {row['source']}\n{'':49}{row.get('name', '')} — {row['note']}")
    print(f'{len(rows)} files inventoried. Nothing was deleted, moved or imported.')


if __name__ == '__main__':
    main()
