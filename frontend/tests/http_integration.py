"""Run after npm run build. Exercises the real Next.js BFF and FastAPI on isolated ports."""
import base64
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend_fixture import MEDIA_PENDING, MEDIA_STUCK, synthetic_photo

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


def encoded(kind='clear', shade=0):
    return base64.b64encode(synthetic_photo(kind, shade)).decode()


def anonymous_media_checks(browser, headers):
    rows = httpx.get(BACKEND+'/listings?community_id=demo', headers={'X-API-Key':ADMIN}).json()
    media = next(row for row in rows if row['title'] == MEDIA_PENDING)
    image = media['images'][0]['id']
    check('anonymous image preview denied', browser.get(f'/api/bql/images/{image}').status_code == 401)
    check('anonymous image upload denied', browser.post(f"/api/bql/listings/{media['id']}/images",
          headers=headers, json={'image_base64':encoded()}).status_code == 401)
    check('anonymous image recheck denied',
          browser.post(f'/api/bql/images/{image}/recheck', headers=headers, json={}).status_code == 401)


def media_checks(browser, headers):
    def listing(title=None, item=None):
        return next(row for row in browser.get('/api/bql/listings').json()
                    if row['title'] == title or row['id'] == item)
    responses = []
    def post(path, **kwargs):
        response = browser.post(path, headers=kwargs.pop('headers', headers), **kwargs)
        responses.append(response)
        return response
    media = listing(MEDIA_PENDING)
    image = media['images'][0]['id']
    preview = browser.get(f'/api/bql/images/{image}')
    responses.append(preview)
    check('authenticated preview streams private JPEG through BFF',
          preview.status_code == 200 and preview.headers['content-type'] == 'image/jpeg'
          and preview.content[:2] == b'\xff\xd8' and 'no-store' in preview.headers['cache-control']
          and preview.headers.get('x-content-type-options') == 'nosniff')
    other = httpx.get(BACKEND+'/listings?community_id=other', headers={'X-API-Key':ADMIN}).json()[0]['images'][0]['id']
    check('cross-community image preview blocked', browser.get(f'/api/bql/images/{other}').status_code == 404)
    check('cross-community image recheck blocked', post(f'/api/bql/images/{other}/recheck', json={}).status_code == 404)
    check('non-hex image path is not proxied', browser.get('/api/bql/images/not-an-image-id').status_code == 404)
    upload = f"/api/bql/listings/{media['id']}/images"
    payload = {'image_base64':encoded('clear', 33)}
    check('cross-site image upload denied (CSRF)',
          post(upload, headers={'Origin':'https://evil.example'}, json=payload).status_code == 403)
    check('cross-site image recheck denied (CSRF)',
          post(f'/api/bql/images/{image}/recheck', headers={'Origin':'https://evil.example'}, json={}).status_code == 403)
    check('image upload requires JSON',
          post(upload, headers={**headers, 'Content-Type':'text/plain'}, content='x').status_code == 415)
    check('caller cannot choose image community', post(upload, json={**payload, 'community_id':'other'}).status_code == 422)
    oversized = b'{"image_base64":"' + b'A' * (6 * 1024 * 1024) + b'"}'
    check('oversized image body rejected before backend',
          post(upload, headers={**headers, 'Content-Type':'application/json'}, content=oversized).status_code == 413)
    check('recheck body bounded to small JSON',
          post(f'/api/bql/images/{image}/recheck', headers={**headers, 'Content-Type':'application/json'},
               content=b'{"x":"' + b'a' * 9000 + b'"}').status_code == 413)
    check('recheck accepts no extra fields', post(f'/api/bql/images/{image}/recheck', json={'status':'clear'}).status_code == 422)
    old_token = media['image_review_token']
    uploaded = post(upload, json=payload)
    check('BQL upload through BFF normalizes and checks image',
          uploaded.status_code == 200 and uploaded.json()['status'] == 'clear')
    after = listing(item=media['id'])
    check('upload adds image and rotates review token',
          len(after['images']) == 3 and after['image_review_token'] != old_token)
    review = f"/api/bql/listings/{media['id']}/review"
    reason = 'QA: đã xem trực tiếp ba ảnh màu tổng hợp, không phải dữ liệu thật'
    check('approval without image review token refused',
          post(review, json={'action':'approve', 'reason':reason, 'manual_image_review':True}).status_code == 409)
    check('approval with pre-upload token refused',
          post(review, json={'action':'approve', 'reason':reason, 'image_review_token':old_token,
                             'manual_image_review':True}).status_code == 409)
    unclear = next(row for row in after['images'] if row['status'] == 'unavailable')
    check('recheck through BFF succeeds', post(f"/api/bql/images/{unclear['id']}/recheck", json={}).status_code == 200)
    rechecked = listing(item=media['id'])
    revision = next(row for row in rechecked['images'] if row['id'] == unclear['id'])['revision']
    check('recheck changes image revision and review token',
          revision != unclear['revision'] and rechecked['image_review_token'] != after['image_review_token'])
    check('token from before recheck is stale',
          post(review, json={'action':'approve', 'reason':reason, 'image_review_token':after['image_review_token'],
                             'manual_image_review':True}).status_code == 409)
    token = rechecked['image_review_token']
    check('unclear image requires manual evidence',
          post(review, json={'action':'approve', 'reason':reason, 'image_review_token':token}).status_code == 409)
    check('manual evidence flag must be boolean',
          post(review, json={'action':'approve', 'reason':reason, 'image_review_token':token,
                             'manual_image_review':'yes'}).status_code == 422)
    stuck = listing(MEDIA_STUCK)
    check('pending image blocks approval even with manual evidence',
          post(f"/api/bql/listings/{stuck['id']}/review", json={'action':'approve', 'reason':reason,
               'image_review_token':stuck['image_review_token'], 'manual_image_review':True}).status_code == 409)
    check('in-flight image cannot be rechecked yet',
          post(f"/api/bql/images/{stuck['images'][0]['id']}/recheck", json={}).status_code == 409)
    approved = post(review, json={'action':'approve', 'reason':reason, 'image_review_token':token,
                                  'manual_image_review':True})
    check('manual image approval queues delivery',
          approved.status_code == 200 and approved.json()['delivery_status'] == 'queued')
    check('approved listing refuses silent new photo', post(upload, json={'image_base64':encoded('clear', 60)}).status_code == 409)
    check('approved listing refuses image recheck', post(f'/api/bql/images/{image}/recheck', json={}).status_code == 409)
    jobs = browser.get('/api/bql/deliveries').json()
    parts = next(row for row in jobs if row['listing_id'] == media['id'])['parts']
    check('approval creates ordered cover/additional/code parts',
          [p['kind'] for p in parts] == ['cover_photo_with_caption', 'additional_photo', 'additional_photo', 'listing_code']
          and all(p['status'] == 'queued' for p in parts))
    multipart = next(row for row in jobs if row['parts'] and row['status'] == 'unknown')
    unknown = next(p for p in multipart['parts'] if p['status'] == 'unknown')
    queued = next(p for p in multipart['parts'] if p['status'] == 'queued')
    reconcile = f"/api/bql/deliveries/{multipart['id']}/reconcile"
    evidence = {'decision':'sent', 'reason':'QA: thấy receipt giả lập của ảnh bìa', 'sent_message_id':'mock-observed-cover'}
    check('multipart reconcile requires part id', post(reconcile, json=evidence).status_code == 422)
    check('multipart reconcile rejects a non-unknown part',
          post(reconcile, json={**evidence, 'part_id':queued['id']}).status_code == 409)
    check('multipart sent decision requires receipt',
          post(reconcile, json={k: v for k, v in {**evidence, 'part_id':unknown['id']}.items()
                                if k != 'sent_message_id'}).status_code == 422)
    resolved = post(reconcile, json={**evidence, 'part_id':unknown['id']})
    check('reconciled cover resumes queue without replay',
          resolved.status_code == 200 and resolved.json()['status'] == 'queued')
    after_parts = next(row for row in browser.get('/api/bql/deliveries').json() if row['id'] == multipart['id'])['parts']
    check('cover receipt recorded as manual; later parts still queued',
          after_parts[0]['status'] == 'sent' and after_parts[0]['transport_mode'] == 'manual'
          and after_parts[0]['sent_message_id'] == 'mock-observed-cover'
          and all(p['status'] == 'queued' for p in after_parts[1:]))
    check('resolved delivery cannot be reconciled twice',
          post(reconcile, json={**evidence, 'part_id':unknown['id']}).status_code == 409)
    check('no media response leaks the admin credential',
          all(ADMIN not in str(r.headers) and ADMIN.encode() not in r.content for r in responses))


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
                anonymous_media_checks(browser, headers)
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
                media_checks(browser, headers)
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
