"""Run after npm run build. Exercises the real Next.js BFF and FastAPI on isolated ports."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / 'frontend'
ORIGIN = 'http://127.0.0.1:3110'
BACKEND = 'http://127.0.0.1:8124'
ADMIN = 'qa-only-admin-sentinel-83d16'
PASSWORD = 'qa-only-password-long-enough'
checks = 0


def check(name, condition):
    global checks
    if not condition:
        raise AssertionError(name)
    checks += 1
    print('PASS', name)


def ready(url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError('QA process exited before readiness; inspect work QA logs')
        try:
            if httpx.get(url, timeout=1).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.2)
    raise RuntimeError('QA server readiness timeout')


def run():
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='http-qa-', dir=ROOT / 'work') as temp:
        qa = Path(temp)
        env = {**os.environ, 'QA_BACKEND_PORT':'8124', 'QA_DATABASE_PATH':str(qa/'db.sqlite'),
               'BACKEND_URL':BACKEND, 'ADMIN_API_KEY':ADMIN, 'BQL_DEMO_PASSWORD':PASSWORD,
               'BQL_SESSION_SECRET':'qa-only-session-secret-at-least-32-characters', 'APP_ORIGIN':ORIGIN,
               'BQL_COMMUNITY_ID':'demo', 'NEXT_TELEMETRY_DISABLED':'1'}
        processes = []
        logs = []
        def launch(command, cwd, variables, label):
            log = (qa/f'{label}.log').open('w', encoding='utf8')
            logs.append(log)
            process = subprocess.Popen(command, cwd=cwd, env=variables, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            processes.append(process)
            return process
        try:
            backend = launch([sys.executable, str(FRONTEND/'tests/backend_fixture.py')], ROOT, env, 'backend')
            ready(BACKEND+'/health', backend)
            node = shutil.which('node')
            command = [node, str(FRONTEND/'node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', '3110']
            server = launch(command, FRONTEND, env, 'next')
            ready(ORIGIN+'/', server)
            headers={'Origin':ORIGIN}
            with httpx.Client(base_url=ORIGIN, timeout=20) as browser:
                check('anonymous data request denied', browser.get('/api/bql/listings').status_code == 401)
                check('protected page redirects', browser.get('/bql').status_code == 307)
                check('login requires same origin', browser.post('/api/auth/login',json={'password':PASSWORD}).status_code == 403)
                check('incorrect password denied', browser.post('/api/auth/login',headers=headers,json={'password':'wrong'}).status_code == 401)
                login = browser.post('/api/auth/login',headers=headers,json={'password':PASSWORD})
                check('configured demo login succeeds', login.status_code == 200)
                cookie = login.headers.get('set-cookie','').lower()
                check('session HttpOnly and SameSite strict', 'httponly' in cookie and 'samesite=strict' in cookie)
                check('cookie contains no password or backend key', PASSWORD not in cookie and ADMIN not in cookie)
                check('authenticated BQL renders', browser.get('/bql').status_code == 200)
                actual = httpx.get(BACKEND+'/stats?community_id=demo',headers={'X-API-Key':ADMIN}).json()
                check('stats reflect real backend data', browser.get('/api/bql/stats').json() == actual)
                wrong_origin = 'http://127.0.0.1:3112'
                wrong_server = launch(command[:-1]+['3112'], FRONTEND,
                    {**env, 'ADMIN_API_KEY':'qa-only-wrong-key', 'APP_ORIGIN':wrong_origin}, 'wrong-key')
                ready(wrong_origin+'/', wrong_server)
                with httpx.Client(base_url=wrong_origin, timeout=20) as misconfigured:
                    misconfigured.post('/api/auth/login',headers={'Origin':wrong_origin},json={'password':PASSWORD})
                    wrong_response = misconfigured.get('/api/bql/stats')
                    check('wrong backend key is a configuration error, not a session logout',
                          wrong_response.status_code == 502 and 'Backend từ chối khóa quản trị' in wrong_response.json()['error'])
                items = browser.get('/api/bql/listings').json()
                pending = next(row for row in items if row['title'] == 'Ghế công thái học')
                check('additive source and advisory moderation reach BFF',
                      pending['source_channel'] == 'legacy' and
                      pending['moderation']['requires_review'] is True and
                      pending['moderation']['risk_score'] is None)
                path = f"/api/bql/listings/{pending['id']}/review"
                check('cross-site review denied', browser.post(path,headers={'Origin':'https://evil.example'},json={'action':'approve','reason':'test'}).status_code == 403)
                check('review reason required', browser.post(path,headers=headers,json={'action':'approve','reason':' '}).status_code == 422)
                check('caller cannot override community', browser.post(path,headers=headers,json={'action':'approve','reason':'test','community_id':'other'}).status_code == 422)
                review = browser.post(path,headers=headers,json={'action':'approve','reason':'Đã kiểm tra dữ liệu QA'})
                check('real approval queues delivery', review.status_code == 200 and review.json()['delivery_status'] == 'queued')
                check('duplicate approval respects backend 409', browser.post(path,headers=headers,json={'action':'approve','reason':'test'}).status_code == 409)
                sensitive = next(row for row in items if row['title'] == 'Máy giặt cửa trước')
                check('sensitive listing respects backend rejection', browser.post(f"/api/bql/listings/{sensitive['id']}/review",headers=headers,json={'action':'approve','reason':'test'}).status_code == 422)
                rejected = next(row for row in items if row['title'] == 'Kệ trang trí')
                check('real reject succeeds', browser.post(f"/api/bql/listings/{rejected['id']}/review",headers=headers,json={'action':'reject','reason':'Cần viết lại'}).json()['status'] == 'rejected')
                jobs = browser.get('/api/bql/deliveries').json()
                check('mock ACK provenance survives BFF validation',
                      any(row['status'] == 'sent' and row['transport_mode'] == 'mock'
                          and row['sent_message_id'].startswith('mock-') for row in jobs))
                unknown = next(row for row in jobs if row['status'] == 'unknown')
                reconcile=browser.post(f"/api/bql/deliveries/{unknown['id']}/reconcile",headers=headers,json={'decision':'not_sent','reason':'Đã dừng worker và kiểm tra dữ liệu mock'})
                check('real reconciliation changes unknown to failed', reconcile.status_code == 200 and reconcile.json()['status'] == 'failed')
                updated = browser.get('/api/bql/deliveries').json()
                check('reconciliation is labelled manual without requeue',
                      next(row for row in updated if row['id'] == unknown['id'])['transport_mode'] == 'manual')
                check('BFF exposes no arbitrary backend proxy', browser.get('/api/bql/events').status_code == 404)
                chunks = (FRONTEND/'.next/static').rglob('*.js')
                check('admin credential absent from browser JS', all(ADMIN.encode() not in p.read_bytes() for p in chunks))
                check('public HTML contains no admin credential', ADMIN not in browser.get('/').text)
                browser.post('/api/auth/logout',headers=headers)
                check('logout denies subsequent admin access', browser.get('/api/bql/stats').status_code == 401)
                browser.post('/api/auth/login',headers=headers,json={'password':PASSWORD})
                backend.terminate();backend.wait(timeout=10)
                check('offline backend produces safe 502', browser.get('/api/bql/stats').status_code == 502)
            missing = {**env, 'ADMIN_API_KEY':'', 'APP_ORIGIN':'http://127.0.0.1:3111'}
            closed = launch(command[:-1]+['3111'], FRONTEND, missing, 'fail-closed')
            ready('http://127.0.0.1:3111/', closed)
            check('missing credentials fail closed', httpx.post('http://127.0.0.1:3111/api/auth/login', headers={'Origin':'http://127.0.0.1:3111'},json={'password':PASSWORD}).status_code == 503)
            print(f'{checks} HTTP integration checks passed; no real outbound Zalo.')
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill();process.wait(timeout=10)
            for log in logs: log.close()


if __name__ == '__main__':
    run()
