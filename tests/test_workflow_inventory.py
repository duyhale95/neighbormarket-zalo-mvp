import json
import tempfile
import unittest
from pathlib import Path

from tools.build_deplao_workflows import build_intake, build_publisher
from tools.workflow_inventory import inventory, redact

ROOT = Path(__file__).resolve().parents[1]


class WorkflowInventoryTests(unittest.TestCase):
    def test_classifies_current_legacy_duplicate_and_keeps_private_data_unparsed(self):
        secret = 'real-looking-bridge-key-123456789'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            publisher = build_publisher(secret, '987654321012', '123456789012', policy_validated=True,
                                        binding_verified=True, version=2)
            (root / 'publisher.json').write_text(json.dumps(publisher), encoding='utf-8')
            (root / 'copy.json').write_text(json.dumps(publisher), encoding='utf-8')
            (root / 'intake.json').write_text(json.dumps(build_intake(secret, '1', '2', binding_verified=True)), encoding='utf-8')
            (root / 'market.db').write_bytes(b'SQLite private')
            (root / 'local-config.json').write_text('{"bridge_key": "x"}', encoding='utf-8')
            legacy = ROOT / 'workflows' / 'meo-meo-auto-reply-private.json'
            rows = {Path(r['source']).name: r for r in inventory([root, legacy])}
        self.assertEqual(rows['copy.json']['class'], 'current-publisher-v2')
        self.assertEqual(rows['publisher.json']['class'], 'duplicate')
        self.assertEqual(rows['intake.json']['class'], 'current-text-intake')
        self.assertEqual(rows['meo-meo-auto-reply-private.json']['class'], 'legacy-standalone-pm-responder')
        self.assertEqual(rows['market.db']['class'], 'private-data')
        self.assertEqual(rows['local-config.json']['class'], 'runtime-config')
        self.assertNotIn(secret, json.dumps(rows))

    def test_redaction_removes_keys_ids_and_media_paths(self):
        graph = build_publisher('another-secret-key-0000000000', '987654321012', '123456789012',
                                policy_validated=True, binding_verified=True, version=2)
        text = json.dumps(redact(graph), ensure_ascii=False)
        for leaked in ('another-secret-key', '987654321012', '123456789012', 'group-media\\\\'):
            self.assertNotIn(leaked, text)


if __name__ == '__main__':
    unittest.main()
