"""Headless UI smoke on an isolated temporary DB; no real Zalo messages."""
import json
import io
from PIL import Image
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.sync_api import sync_playwright, expect


def main():
    with tempfile.TemporaryDirectory() as folder:
        env = os.environ.copy()
        env.pop('OPENAI_API_KEY',None)
        env.update(BRIDGE_API_KEY=secrets.token_hex(32), ADMIN_API_KEY=secrets.token_hex(32),
                   DATABASE_PATH=str(Path(folder)/'ui.db'), DEMO_COMMUNITY_ID='demo', ZALO_GROUP_ID='12345', ZALO_GROUP_NAME='Nhóm thử')
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        server = subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:from_environment','--factory',
                                   '--host','127.0.0.1','--port',str(port)], env=env,
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            with httpx.Client(base_url=url) as api:
                for _ in range(80):
                    try:
                        if api.get('/health').status_code == 200: break
                    except httpx.ConnectError: pass
                    time.sleep(.1)
                else: raise RuntimeError('Test server not ready')
                h = {'X-API-Key':env['BRIDGE_API_KEY'],'X-Publisher-Version':'2'}
                def send(text, event_id):
                    r = api.post('/events',headers=h,json=dict(event_id=event_id,community_id='demo',sender_id='test',text=text))
                    r.raise_for_status();return r.json()
                title='<img src=x onerror=window.__xss=1>'
                id=send('ban '+title+' | 500000 | Cũ, còn tốt','one')['listing_id']
                send('xacnhan '+id,'two')
                with sync_playwright() as p:
                    browser = p.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width':1366,'height':960})
                    errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
                    page.goto(url+'/admin');page.wait_for_load_state('networkidle')
                    page.get_by_label('Khóa quản trị local').fill(env['ADMIN_API_KEY'])
                    page.get_by_role('button',name='Tải danh sách').click()
                    expect(page.get_by_role('heading',name=title)).to_be_visible()
                    assert page.evaluate('window.__xss') is None
                    page.context.grant_permissions(['clipboard-read','clipboard-write'],origin=url)
                    page.get_by_role('button',name='Sao chép mã tin',exact=True).click()
                    assert page.evaluate('navigator.clipboard.readText()')==id
                    image=io.BytesIO();Image.new('RGB',(32,32),'blue').save(image,format='PNG')
                    page.get_by_label('Ảnh cho '+id).set_input_files({'name':'test.png','mimeType':'image/png','buffer':image.getvalue()})
                    page.get_by_role('button',name='Tải ảnh và kiểm tra an toàn').click()
                    expect(page.get_by_text('Chưa cấu hình dịch vụ kiểm duyệt',exact=True)).to_be_visible()
                    page.get_by_role('button',name='Xem ảnh',exact=True).click()
                    expect(page.get_by_role('img',name='Ảnh sản phẩm cư dân gửi')).to_be_visible()
                    page.get_by_label('Lý do xử lý '+id).fill('Kiểm tra UI bằng dữ liệu tổng hợp')
                    page.get_by_role('button',name='Duyệt tin',exact=True).click()
                    expect(page.locator('#notice')).to_contain_text('BQL cần xem ảnh')
                    page.get_by_label('Đã kiểm tra ảnh '+id).check()
                    page.get_by_role('button',name='Duyệt tin',exact=True).click()
                    expect(page.get_by_role('button',name='Sao chép tin đăng nhóm')).to_be_visible()
                    expect(page.get_by_text('Nhóm thử: Đang chờ đăng',exact=True)).to_be_visible()
                    for part in ('post','code'):
                        job=api.post('/group-publications/claim',headers=h).json()
                        assert job['ready'] and job['part']==part
                        if part=='post':assert job['has_image'] and Path(job['image_path']).is_file()
                        if part=='code':assert job['message']==id
                        receipt=api.post('/group-publications/'+job['job_id']+'/ack',headers=h,json={'token':job['token'],'message_id':'123456'})
                        receipt.raise_for_status()
                    page.get_by_role('button',name='Tải danh sách').click()
                    expect(page.get_by_text('Nhóm thử: Đã đăng bài, ảnh (nếu có) và mã tin',exact=True)).to_be_visible()
                    root=Path('private/qa');root.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(root/'admin-desktop.png'),full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.screenshot(path=str(root/'admin-mobile.png'),full_page=True)
                    # Regression: a response arriving after lock must not reveal rows.
                    rows=api.get('/listings?community_id=demo',headers={'X-API-Key':env['ADMIN_API_KEY']}).json()
                    held=[]
                    page.route('**/listings?*',lambda route:held.append(route))
                    with page.expect_request('**/listings?*'):
                        page.get_by_role('button',name='Tải danh sách').click()
                    page.get_by_role('button',name='Khóa bảng',exact=True).click()
                    assert held
                    held[0].fulfill(status=200,content_type='application/json',body=json.dumps(rows))
                    page.wait_for_load_state('networkidle')
                    expect(page.get_by_role('heading',name=title)).to_have_count(0)
                    expect(page.locator('#notice')).to_have_text('Đã khóa bảng.')
                    assert not errors,errors
                    browser.close()
            print('UI_OK: approval, XSS text rendering, mobile width, lock/stale-response regression; synthetic data only')
        finally:
            server.terminate();server.wait(timeout=10)


if __name__=='__main__':main()
