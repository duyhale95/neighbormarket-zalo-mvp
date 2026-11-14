"""Isolated fake data for UI/HTTP QA; binds only localhost, never sends Zalo.

Every image is a generated solid-colour square. The moderator is a synthetic
stub keyed on colour, NOT OpenAI and NOT image understanding.
"""
import base64
import io
import os
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from PIL import Image
import uvicorn
from backend.app import create_app

ADMIN = 'qa-only-admin-sentinel-83d16'
BRIDGE = 'qa-only-bridge-sentinel-48c72'
MEDIA_PENDING = 'Xe đạp trẻ em (ảnh giả lập)'
MEDIA_STUCK = 'Nồi cơm điện (ảnh đang kiểm tra giả lập)'
MEDIA_UNKNOWN = 'Quạt đứng (ảnh giả lập)'
MEDIA_APPROVED = 'Tủ lạnh mini (ảnh giả lập)'
SYNTHETIC_COLOURS = {'clear': (214, 168, 74), 'unavailable': (40, 70, 200), 'flagged': (210, 30, 30)}


def synthetic_photo(kind: str = 'clear', shade: int = 0) -> bytes:
    red, green, blue = SYNTHETIC_COLOURS[kind]
    stream = io.BytesIO()
    Image.new('RGB', (96, 72), (red, min(green + shade, 255), blue)).save(stream, format='PNG')
    return stream.getvalue()


class SyntheticModerator:
    """Deterministic QA stub: gold=clear, blue=unavailable, red=flagged."""

    def check(self, data, mime, text):
        with Image.open(io.BytesIO(data)) as image:
            red, green, blue = image.convert('RGB').getpixel((0, 0))
        if red > 160 and green < 90:
            return {'status': 'flagged', 'categories': ['violence'], 'model': 'SYNTHETIC-QA-STUB'}
        if blue > red:
            return {'status': 'unavailable', 'categories': [], 'model': 'unavailable'}
        return {'status': 'clear', 'categories': [], 'model': 'SYNTHETIC-QA-STUB'}


def build(path: str):
    os.environ['AI_ENABLED'] = 'false'
    app = create_app(path, BRIDGE, ADMIN, target_group_id='mock-legit-group',
                     image_moderator=SyntheticModerator())
    with TestClient(app) as client:
        admin = {'X-API-Key': ADMIN}
        bridge = {'X-API-Key': BRIDGE}
        sequence = 0

        def event(text, community='demo'):
            nonlocal sequence
            sequence += 1
            response = client.post('/events', headers=bridge, json={
                'event_id': f'ui-fixture-{sequence}', 'community_id': community,
                'sender_id': 'resident-demo-only', 'text': text})
            response.raise_for_status()
            return response.json()

        def media_listing(title, price, condition, kinds, community='demo'):
            item = event(f'ban {title} | {price} | {condition}', community)['listing_id']
            for shade, kind in enumerate(kinds):
                client.post(f'/listings/{item}/images', headers=admin, json={
                    'community_id': community,
                    'image_base64': base64.b64encode(synthetic_photo(kind, shade * 9)).decode(),
                }).raise_for_status()
            event(f'xacnhan {item}', community)
            return item

        def approve_with_token(item):
            token = next(row for row in client.get('/listings?community_id=demo', headers=admin).json()
                         if row['id'] == item)['image_review_token']
            client.post(f'/listings/{item}/review', headers=admin, json={
                'community_id': 'demo', 'action': 'approve', 'image_review_token': token,
                'reason': 'Dữ liệu QA giả lập: đã xem ảnh màu tổng hợp'}).raise_for_status()

        v2 = {**bridge, 'X-Publisher-Version': '2'}

        def claim_part():
            job = client.post('/deliveries/claim', headers=v2)
            job.raise_for_status()
            return job.json()

        def ack_part(job, receipt):
            client.post(f"/deliveries/{job['delivery_id']}/sent", headers=bridge, json={
                'claim_token': job['claim_token'], 'part_id': job['part_id'],
                'sent_message_id': receipt, 'transport_mode': 'mock'}).raise_for_status()

        # Media fixtures first, in photos_v2 mode, so no legacy queued job is claimed by v2.
        app.state.publication_mode = 'photos_v2'
        unknown = media_listing(MEDIA_UNKNOWN, 300000, 'Còn mới', ['clear', 'clear'])
        approve_with_token(unknown)
        cover = claim_part()
        client.post(f"/deliveries/{cover['delivery_id']}/failure", headers=bridge, json={
            'claim_token': cover['claim_token'], 'part_id': cover['part_id'], 'outcome': 'unknown',
            'error': 'timeout', 'transport_mode': 'mock'}).raise_for_status()
        sold = media_listing(MEDIA_APPROVED, 1500000, 'Đã dùng 2 năm', ['clear', 'clear'])
        approve_with_token(sold)
        for index in range(3):
            ack_part(claim_part(), f'mock-fixture-part-{index + 1}')
        event(f'daban {sold}')
        media_listing(MEDIA_PENDING, 650000, 'Đã dùng 1 năm', ['clear', 'unavailable'])
        stuck = media_listing(MEDIA_STUCK, 400000, 'Còn tốt', ['clear'])
        with closing(sqlite3.connect(path)) as db:
            # Simulate an in-flight check that has not timed out yet (QA only).
            db.execute("UPDATE listing_images SET status='pending', updated_at=? WHERE listing_id=?",
                       (time.time() + 86400, stuck))
            db.commit()
        media_listing('Ảnh cộng đồng khác (giả lập)', 100000, 'Còn tốt', ['clear'], 'other')
        app.state.publication_mode = 'single'

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
                        json={'claim_token':job['claim_token'], 'sent_message_id':'mock-only-message', 'transport_mode':'mock'}).raise_for_status()
                else:
                    client.post(f"/deliveries/{job['delivery_id']}/failure", headers=bridge,
                        json={'claim_token':job['claim_token'], 'outcome':'unknown' if delivery == 'unknown' else 'not_sent',
                              'error':'timeout' if delivery == 'unknown' else 'send_rejected',
                              'transport_mode':'mock'}).raise_for_status()
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
        # New BQL approvals during QA create ordered photo/code parts.
        app.state.publication_mode = 'photos_v2'
    return app


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2] / 'work'
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ui-fixture-', dir=root) as temp:
        db = os.getenv('QA_DATABASE_PATH', str(Path(temp) / 'qa.db'))
        uvicorn.run(build(db), host='127.0.0.1', port=int(os.getenv('QA_BACKEND_PORT', '8123')), log_level='warning')
