import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
import httpx
from PIL import Image
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.ai import Analysis, GeminiExtractor, AIUnavailable, ImageInput, validate_image


def picture():
    out = io.BytesIO()
    Image.new('RGB', (16, 16), 'blue').save(out, format='PNG')
    return base64.b64encode(out.getvalue()).decode()


class ProviderTests(unittest.TestCase):
    def test_gemini_structured_and_inline_image(self):
        def handle(req):
            self.assertEqual(req.headers['x-goog-api-key'], 'test-secret')
            body = json.loads(req.content)
            self.assertEqual(body['generationConfig']['responseMimeType'], 'application/json')
            self.assertIn('inlineData', body['contents'][0]['parts'][1])
            output = Analysis(intent='sell', title='Ghế', price_vnd=500000).model_dump_json()
            return httpx.Response(200, json={'candidates':[{'content':{'parts':[{'text':output}]}}]})
        ai = GeminiExtractor('test-secret', 'test-model', transport=httpx.MockTransport(handle))
        result = ai.extract('bán ghế 500k', ImageInput(mime_type='image/png', data=picture()), {})
        self.assertEqual(result.title, 'Ghế')
        self.assertIsNone(result.condition)

    def test_bad_model_responses_are_sanitized(self):
        for response in [httpx.Response(401, text='secret'), httpx.Response(200, json={}),
                         httpx.Response(200, json={'candidates':[{'content':{'parts':[{'text':'not json'}]}}]})]:
            with self.subTest(response=response):
                ai = GeminiExtractor('secret', 'test', transport=httpx.MockTransport(lambda req: response))
                with self.assertRaises(AIUnavailable) as ex:
                    ai.extract('hello', None, {})
                self.assertNotIn('secret', str(ex.exception))

    def test_images_and_model_values_are_validated(self):
        validate_image(ImageInput(mime_type='image/png', data=picture()))
        for data in ['bad', base64.b64encode(b'not an image').decode()]:
            with self.assertRaises(ValueError):
                validate_image(ImageInput(mime_type='image/png', data=data))
        with self.assertRaises(ValueError):
            Analysis(intent='sell', price_vnd=-1)
        with self.assertRaises(ValueError):
            Analysis(intent='sell', price_vnd=True)


class FakeExtractor:
    def __init__(self):
        self.calls = []
    def extract(self, text, image, previous):
        self.calls.append((text, image, previous))
        if text == 'fail':
            raise AIUnavailable('Unavailable')
        if text == 'mua ghế':
            return Analysis(intent='buy', query='ghế')
        if text == 'cũ, 500k':
            return Analysis(intent='sell', title=previous.get('title'), price_vnd=500000, condition='Đã dùng')
        return Analysis(intent='sell', title='Ghế', risk='review', reasons=['Cần BQL kiểm tra'])


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ai = FakeExtractor()
        self.client = TestClient(create_app(Path(self.tmp.name)/'market.db', 'bridge', 'admin', extractor=self.ai))
        self.seq = 0
    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()
    def send(self, text, **extra):
        self.seq += 1
        data = dict(event_id=str(self.seq), community_id='demo', sender_id='seller', text=text)
        data.update(extra)
        return self.client.post('/ai/events', json=data, headers={'X-API-Key':'bridge'})

    def test_multiturn_confirmation_review_image_and_search(self):
        first = self.send('bán ghế', image={'mime_type':'image/png','data':picture()}).json()
        self.assertIn('price_vnd', first['missing_fields'])
        self.assertEqual(first['status'], 'incomplete')
        id = first['listing_id']
        self.assertEqual(self.send(f'xacnhan {id}').status_code, 422)
        done = self.send('cũ, 500k').json()
        self.assertEqual(done['listing_id'], id)
        self.assertEqual(done['status'], 'draft')
        self.assertEqual(self.send(f'xacnhan {id}').json()['status'], 'pending')
        self.assertEqual(self.send('mua ghế').json()['listings'], [])
        listing = self.client.get('/listings?community_id=demo', headers={'X-API-Key':'admin'}).json()[0]
        self.assertEqual(listing['ai']['risk'], 'review')
        self.assertTrue(listing['has_image'])
        photo = self.client.get(f'/listings/{id}/image?community_id=demo', headers={'X-API-Key':'admin'})
        self.assertEqual(photo.headers['content-type'], 'image/png')
        self.assertEqual(self.client.get(f'/listings/{id}/image?community_id=other', headers={'X-API-Key':'admin'}).status_code, 404)
        self.assertEqual(self.client.get(f'/listings/{id}/image?community_id=demo', headers={'X-API-Key':'bridge'}).status_code, 401)
        self.client.post(f'/listings/{id}/review', headers={'X-API-Key':'admin'}, json=dict(community_id='demo', action='approve', reason='Đã kiểm tra'))
        self.assertEqual(self.send('mua ghế').json()['listings'][0]['id'], id)

    def test_duplicates_isolation_and_no_self_calls(self):
        first = self.send('bán ghế', event_id='same').json()
        self.assertEqual(self.send('different', event_id='same').json(), first)
        self.assertEqual(len(self.ai.calls), 1)
        self.send('cũ, 500k', sender_id='other')
        self.assertEqual(self.ai.calls[-1][2], {})
        self.send('cũ, 500k', community_id='other')
        self.assertEqual(self.ai.calls[-1][2], {})
        self.send('hello', is_self=True)
        self.assertEqual(len(self.ai.calls), 3)

    def test_errors_do_not_create_listings(self):
        self.assertEqual(self.send('fail').status_code, 503)
        self.assertEqual(self.send('bad image', image={'mime_type':'image/png', 'data':'bad'}).status_code, 422)
        self.assertEqual(self.client.get('/listings?community_id=demo', headers={'X-API-Key':'admin'}).json(), [])

    def test_ai_unconfigured_and_dashboard_available(self):
        other = TestClient(create_app(Path(self.tmp.name)/'other.db', 'bridge', 'admin'))
        self.assertEqual(other.get('/admin').status_code, 200)
        r = other.post('/ai/events', headers={'X-API-Key':'bridge'}, json=dict(event_id='x', community_id='demo', sender_id='u', text='bán ghế'))
        self.assertEqual(r.status_code, 503)
        other.close()
