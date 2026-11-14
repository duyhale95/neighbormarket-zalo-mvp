"""Isolated fake data for UI/HTTP QA; binds only localhost, never sends Zalo."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
import uvicorn
from backend.app import create_app

ADMIN = 'qa-only-admin-sentinel-83d16'
BRIDGE = 'qa-only-bridge-sentinel-48c72'


def build(path: str):
    app = create_app(path, BRIDGE, ADMIN, target_group_id='mock-legit-group')
    with TestClient(app) as client:
        admin = {'X-API-Key': ADMIN}
        bridge = {'X-API-Key': BRIDGE}
        sequence = 0

        def event(text):
            nonlocal sequence
            sequence += 1
            response = client.post('/events', headers=bridge, json={
                'event_id': f'ui-fixture-{sequence}', 'community_id': 'demo',
                'sender_id': 'resident-demo-only', 'text': text})
            response.raise_for_status()
            return response.json()

        def listing(title, price, condition, status='pending', delivery=None):
            item = event(f'ban {title} | {price} | {condition}')['listing_id']
            event(f'xacnhan {item}')
            if status != 'pending':
                client.post(f'/listings/{item}/review', headers=admin, json={
                    'community_id':'demo', 'action':'reject' if status == 'rejected' else 'approve',
                    'reason':'Dữ liệu QA giả lập'}).raise_for_status()
            if delivery:
                job = client.post('/deliveries/claim', headers=bridge).json()
                if delivery == 'sent':
                    client.post(f"/deliveries/{job['delivery_id']}/sent", headers=bridge,
                        json={'claim_token':job['claim_token'], 'sent_message_id':'mock-only-message'}).raise_for_status()
                else:
                    client.post(f"/deliveries/{job['delivery_id']}/failure", headers=bridge,
                        json={'claim_token':job['claim_token'], 'outcome':'unknown' if delivery == 'unknown' else 'not_sent',
                              'error':'timeout' if delivery == 'unknown' else 'send_rejected'}).raise_for_status()
            if status == 'sold':
                event(f'daban {item}')

        listing('Kệ sách gỗ sồi', 350000, 'Đã dùng 6 tháng, còn tốt', 'approved', 'sent')
        listing('Đèn bàn đọc sách', 120000, 'Còn tốt', 'approved', 'unknown')
        listing('Tủ giày nhỏ', 600000, 'Đã dùng 1 năm', 'approved', 'failed')
        listing('Bộ ly thủy tinh', 150000, 'Đã qua sử dụng', 'sold', 'sent')
        listing('Bàn học gỗ', 450000, 'Đã dùng 1 năm', 'approved')
        listing('Ghế công thái học', 800000, 'Đã sử dụng 8 tháng, còn tốt')
        listing('Máy giặt cửa trước', 2200000, 'Số giả để thử lọc: 0901234567')
        listing('Kệ trang trí', 250000, 'Còn mới')
        listing('Bài đăng không phù hợp', 100000, 'Nội dung cần viết lại', 'rejected')
    return app


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2] / 'work'
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ui-fixture-', dir=root) as temp:
        db = os.getenv('QA_DATABASE_PATH', str(Path(temp) / 'qa.db'))
        uvicorn.run(build(db), host='127.0.0.1', port=int(os.getenv('QA_BACKEND_PORT', '8123')), log_level='warning')
