"""Synthetic product images only; all model/CDN I/O mocked."""
import base64
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from pillow_heif import from_pillow
from backend.app import create_app


def photo(color='gold', fmt='PNG', size=(40, 30)):
    stream = io.BytesIO()
    image = Image.new('RGB', size, color)
    exif = Image.Exif(); exif[270] = 'sensitive synthetic metadata'
    image.save(stream, format=fmt, exif=exif)
    return stream.getvalue()


class Moderator:
    def __init__(self, status='clear'): self.status = status
    def check(self, data, mime, text):
        return {'status': self.status, 'categories': ['violence'] if self.status == 'flagged' else [], 'model': 'mock-moderation'}


class MediaImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'market.db'
        self.moderator = Moderator()
        self.client = TestClient(create_app(self.path, 'bridge', 'admin', target_group_id='legit', image_moderator=self.moderator))
        self.admin = {'X-API-Key':'admin'}; self.bridge = {'X-API-Key':'bridge'}; self.seq = 0
        self.item = self.event('ban Ghế | 800000 | dùng 6 tháng').json()['listing_id']

    def tearDown(self): self.client.close(); self.temp.cleanup()
    def event(self, text, sender='seller', community='demo'):
        self.seq += 1
        return self.client.post('/events',headers=self.bridge,json={'event_id':str(self.seq),'sender_id':sender,'community_id':community,'text':text})
    def upload(self, data=None, community='demo', item=None):
        return self.client.post(f'/listings/{item or self.item}/images',headers=self.admin,
            json={'community_id':community,'image_base64':base64.b64encode(data if data is not None else photo()).decode()})
    def record(self): return next(r for r in self.client.get('/listings?community_id=demo',headers=self.admin).json() if r['id']==self.item)
    def review(self, **extra):
        return self.client.post(f'/listings/{self.item}/review',headers=self.admin,json={'community_id':'demo','action':'approve','reason':'Đã trực tiếp xem ảnh tổng hợp',**extra})

    def test_valid_formats_private_preview_exif_dedup_scope_and_auth(self):
        for fmt in ('PNG','JPEG','WEBP'):
            self.assertEqual(self.upload(photo(fmt=fmt)).status_code,200)
        result=self.upload().json()
        self.assertEqual(result['status'],'clear')
        self.assertEqual(self.upload().json()['image_id'],result['image_id'])
        url=f"/images/{result['image_id']}?community_id=demo"
        self.assertEqual(self.client.get(url).status_code,401)
        self.assertEqual(self.client.get(url.replace('demo','other'),headers=self.admin).status_code,404)
        response=self.client.get(url,headers=self.admin)
        self.assertEqual(response.headers['content-type'],'image/jpeg')
        self.assertEqual(response.headers['cache-control'],'private, no-store')
        with Image.open(io.BytesIO(response.content)) as normalized:
            self.assertFalse(normalized.getexif())
        self.assertEqual(self.upload(community='other').status_code,404)

    def test_invalid_oversized_upload_and_excess_images_are_rejected(self):
        self.assertEqual(self.upload(b'not an image').status_code,422)
        self.assertEqual(self.upload(b'x'*(4*1024*1024+1)).status_code,422)
        for i in range(5): self.assertEqual(self.upload(photo((i*30,10,20))).status_code,200)
        self.assertEqual(self.upload(photo('blue')).status_code,409)

    def test_animated_gif_is_stored_as_the_first_frame(self):
        source = io.BytesIO()
        first = Image.new('RGB', (32, 32), 'red')
        first.save(source, format='GIF', save_all=True,
                   append_images=[Image.new('RGB', (32, 32), 'blue')], duration=100)
        response = self.upload(source.getvalue())
        response.raise_for_status()
        saved = self.client.get(f"/images/{response.json()['image_id']}?community_id=demo",headers=self.admin)
        with Image.open(io.BytesIO(saved.content)) as result:
            self.assertEqual(result.format, 'JPEG')
            self.assertGreater(result.getpixel((0, 0))[0], 200)

    def test_heic_is_normalized_for_bql(self):
        source = io.BytesIO()
        from_pillow(Image.new('RGB', (32, 32), 'blue')).save(source)
        response = self.upload(source.getvalue())
        response.raise_for_status()
        preview = self.client.get(f"/images/{response.json()['image_id']}?community_id=demo",
                                  headers=self.admin)
        self.assertEqual(preview.headers['content-type'], 'image/jpeg')

    def test_review_token_stale_recheck_manual_evidence_and_immutability(self):
        self.moderator.status='unavailable'
        image=self.upload().json()['image_id']
        old=self.record()['image_review_token']
        self.event('sửa giá 700k')
        self.event('ok')
        self.assertEqual(self.review(image_review_token=old,manual_image_review=True).status_code,409)
        current=self.record()
        self.assertEqual(current['images'][0]['status'],'stale')
        self.assertEqual(self.review(image_review_token=current['image_review_token']).status_code,409)
        result=self.review(image_review_token=current['image_review_token'],manual_image_review=True)
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.upload(photo('blue')).status_code,409)
        self.assertEqual(self.client.post(f'/images/{image}/recheck?community_id=demo',headers=self.admin).status_code,409)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM image_reviews').fetchone()[0],1)

    def test_clear_still_requires_bql_and_pending_or_error_never_auto_passes(self):
        self.upload(); self.event('ok')
        self.assertEqual(self.client.post('/deliveries/claim',headers=self.bridge).status_code,204)
        self.assertEqual(self.review().status_code,409)
        current=self.record()
        self.assertEqual(self.review(image_review_token=current['image_review_token']).status_code,200)

    def test_image_event_disabled_by_default_and_context_ownership_guarded(self):
        data={'event_id':'image-1','community_id':'demo','sender_id':'seller','url':'https://photo-zalo.zadn.vn/a.jpg'}
        self.assertEqual(self.client.post('/image-events',headers=self.bridge,json=data).status_code,503)
        from backend.images import ImageStore
        store=self.client.app.state.images
        with patch('backend.images.fetch_zalo',return_value=photo()) as fetch:
            with self.assertRaises(Exception): store.receive_zalo(data['url'],'other','seller','e1')
            with self.assertRaises(Exception): store.receive_zalo(data['url'],'demo','intruder','e1')
            fetch.assert_not_called()
            result=store.receive_zalo(data['url'],'demo','seller','e1')
            self.assertEqual(store.receive_zalo(data['url'],'demo','seller','e1'),result)
            self.assertEqual(fetch.call_count,1)
        def switch_item(url):
            self.event('hủy'); self.event('ban Bàn | 900000 | mới')
            return photo('blue')
        with patch('backend.images.fetch_zalo',side_effect=switch_item):
            with self.assertRaises(Exception): store.receive_zalo(data['url'],'demo','seller','e2')
        self.assertEqual(len(self.record()['images']),1)
