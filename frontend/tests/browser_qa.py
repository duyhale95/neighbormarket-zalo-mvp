"""Browser QA for BQL image review and delivery parts. Synthetic fixture data only.

Run after `npm run build`, from the repository root:
    .\\.venv\\Scripts\\python.exe -m pip install playwright   # QA-only, not a runtime dependency
    .\\.venv\\Scripts\\python.exe frontend\\tests\\browser_qa.py [--out docs/qa]

Uses the installed Microsoft Edge (Playwright channel "msedge"); no browser download.
Screenshots carry a visible "DỮ LIỆU GIẢ LẬP" banner. No Zalo, model or private data.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend_fixture import ADMIN, MEDIA_PENDING, synthetic_photo
from http_integration import PASSWORD, ready

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / 'frontend'
ORIGIN = 'http://127.0.0.1:3140'
BACKEND = 'http://127.0.0.1:8127'
VIEWPORTS = [(360, 800), (768, 1024), (1440, 900)]
BANNER = 'DỮ LIỆU GIẢ LẬP · QA — không phải cư dân thật · không gửi Zalo · moderator là stub'
LABEL_JS = """(text) => {
  const make = () => { const d = document.createElement('div'); d.textContent = text; d.className = 'qa-synthetic-label';
    d.style.cssText = 'position:sticky;top:0;z-index:2147483647;background:#7a1d1d;color:#fff;font:600 12px/1.4 sans-serif;padding:6px 10px;text-align:center;letter-spacing:.02em'; return d; };
  document.querySelectorAll('.qa-synthetic-label').forEach((n) => n.remove());
  document.body.prepend(make());
  const dialog = document.querySelector('dialog[open]'); if (dialog) dialog.prepend(make());
}"""
results = []


def check(name, condition, detail=''):
    results.append((name, bool(condition)))
    print(('PASS ' if condition else 'FAIL ') + name + (f' — {detail}' if detail and not condition else ''))


def overflow(page):
    return page.evaluate('() => document.documentElement.scrollWidth - window.innerWidth')


def images_loaded(page, scope):
    return page.evaluate("""(scope) => [...document.querySelectorAll(scope + ' img')]
        .every((img) => img.complete && img.naturalWidth > 0)""", scope)


def run(out: Path):
    from playwright.sync_api import sync_playwright
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='browser-qa-', dir=ROOT / 'work') as temp:
        qa = Path(temp)
        env = {**os.environ, 'QA_BACKEND_PORT': '8127', 'QA_DATABASE_PATH': str(qa / 'db.sqlite'),
               'BACKEND_URL': BACKEND, 'ADMIN_API_KEY': ADMIN, 'BQL_DEMO_PASSWORD': PASSWORD,
               'BQL_SESSION_SECRET': 'qa-only-session-secret-at-least-32-characters', 'APP_ORIGIN': ORIGIN,
               'BQL_COMMUNITY_ID': 'demo', 'NEXT_TELEMETRY_DISABLED': '1'}
        upload = qa / 'synthetic-upload.png'
        upload.write_bytes(synthetic_photo('clear', 70))
        processes, logs = [], []
        try:
            for command, cwd, label in (
                    ([sys.executable, str(FRONTEND / 'tests/backend_fixture.py')], ROOT, 'backend'),
                    ([shutil.which('node'), str(FRONTEND / 'node_modules/next/dist/bin/next'), 'start',
                      '--hostname', '127.0.0.1', '--port', '3140'], FRONTEND, 'next')):
                log = (qa / f'{label}.log').open('w', encoding='utf8'); logs.append(log)
                processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log))
                ready((BACKEND + '/health') if label == 'backend' else (ORIGIN + '/'), processes[-1])
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                for width, height in VIEWPORTS:
                    context = browser.new_context(viewport={'width': width, 'height': height}, locale='vi-VN')
                    page = context.new_page()
                    urls, errors = [], []
                    page.on('request', lambda r: urls.append(r.url))
                    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
                    page.goto(ORIGIN + '/bql/login')
                    page.fill('#password', PASSWORD)
                    page.click('button[type=submit]')
                    page.wait_for_url(ORIGIN + '/bql')
                    page.goto(ORIGIN + '/bql/listings')
                    page.get_by_label(f'Xem {MEDIA_PENDING}').click()
                    dialog = page.locator('dialog[open]')
                    dialog.wait_for()
                    page.wait_for_function("() => [...document.querySelectorAll('dialog[open] img')].length >= 2")
                    page.wait_for_load_state('networkidle')
                    check(f'{width}px: private thumbnails load through BFF', images_loaded(page, 'dialog[open]'))
                    check(f'{width}px: unclear photo label shown', dialog.get_by_text('Chưa kiểm tra tự động').count() >= 1)
                    approve = dialog.get_by_role('button', name='Phê duyệt tin')
                    dialog.locator('#review-reason').fill('QA: đã xem ảnh màu tổng hợp')
                    check(f'{width}px: approve disabled until manual evidence', approve.is_disabled())
                    dialog.locator('input[type=checkbox]').check()
                    check(f'{width}px: approve enabled after manual evidence', approve.is_enabled())
                    dialog.get_by_label('Xem ảnh sản phẩm 1').click()
                    page.wait_for_function("() => [...document.querySelectorAll('dialog[open] img')].length >= 3")
                    page.wait_for_load_state('networkidle')
                    check(f'{width}px: enlarged preview loads', images_loaded(page, 'dialog[open]'))
                    check(f'{width}px: listings page has no horizontal overflow', overflow(page) <= 1, str(overflow(page)))
                    page.evaluate(LABEL_JS, BANNER)
                    page.screenshot(path=str(out / f'bql-image-review-{width}.png'))
                    if width == 1440:
                        dialog.locator('input[type=file]').set_input_files(str(upload))
                        page.wait_for_function("() => [...document.querySelectorAll('dialog[open] article')].length >= 3")
                        check('1440px: browser upload adds a third image', dialog.locator('article').count() == 3)
                        check('1440px: manual evidence reset after image change',
                              not dialog.locator('input[type=checkbox]').is_checked())
                        dialog.locator('input[type=checkbox]').check()
                        approve.click()
                        dialog.get_by_role('button', name='Xác nhận phê duyệt').click()
                        page.get_by_text('Đã duyệt tin và tạo delivery').wait_for()
                        check('1440px: approval with current token and manual evidence succeeds', True)
                    page.goto(ORIGIN + '/bql/deliveries')
                    page.locator('details').first.wait_for()
                    if width == 1440:
                        buttons = page.get_by_role('button', name='Đối soát', exact=True)
                        for index in range(buttons.count()):
                            buttons.nth(index).click()
                            reconcile = page.locator('dialog[open]')
                            if reconcile.get_by_text('Đối soát riêng phần').count():
                                break
                            reconcile.get_by_role('button', name='Hủy').click()
                        check('1440px: reconcile dialog names the unknown part',
                              reconcile.get_by_text('Ảnh bìa kèm nội dung').count() == 1)
                        reconcile.locator('#decision').select_option('sent')
                        reconcile.locator('#sent-id').fill('mock-observed-in-browser')
                        reconcile.locator('#reconcile-reason').fill('QA: receipt giả lập quan sát được')
                        reconcile.locator('input[type=checkbox]').check()
                        page.evaluate(LABEL_JS, BANNER)
                        page.screenshot(path=str(out / 'bql-part-reconcile-1440.png'))
                        reconcile.get_by_role('button', name='Xác nhận đối soát').click()
                        page.get_by_text('Đã lưu đối soát').wait_for()
                        check('1440px: part reconciliation saved from the browser', True)
                    page.evaluate("() => document.querySelectorAll('details').forEach((d) => { d.open = true; })")
                    page.get_by_text('Ảnh bìa kèm nội dung').first.wait_for()
                    check(f'{width}px: delivery parts and receipts visible',
                          page.get_by_text('Receipt: mock-fixture-part-1').count() >= 1)
                    check(f'{width}px: deliveries page has no horizontal overflow', overflow(page) <= 1, str(overflow(page)))
                    page.evaluate(LABEL_JS, BANNER)
                    page.screenshot(path=str(out / f'bql-delivery-parts-{width}.png'), full_page=True)
                    check(f'{width}px: no browser request carries admin key', all(ADMIN not in u for u in urls))
                    check(f'{width}px: images requested only via same-origin BFF',
                          all(u.startswith(ORIGIN) for u in urls if '/images/' in u))
                    check(f'{width}px: no console errors', not errors, '; '.join(errors)[:300])
                    context.close()
                browser.close()
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
            for log in logs: log.close()
    failed = [name for name, ok in results if not ok]
    print(f'{len(results) - len(failed)}/{len(results)} browser checks passed; screenshots in {out}')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(ROOT / 'work' / 'browser-qa'))
    run(Path(parser.parse_args().out).resolve())
