import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.intake_bridge import create_intake_app


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backend = TestClient(create_app(Path(self.tmp.name) / 'db.sqlite', 'backend-secret', 'admin-secret'))
        self.app = create_intake_app('http://backend', 'backend-secret', 'intake-secret', 'demo', client=self.backend)
        self.client = TestClient(self.app)
        self.headers = {'X-Intake-Key': 'intake-secret'}
        self.event = {'message_id': 'stable-1', 'sender_id': 'seller', 'thread_id': 'chat-1',
                      'thread_type': 'private', 'is_self': False,
                      'text': 'ban Ghế "đẹp" \\ gỗ | 500000 | còn tốt\nnhé'}

    def tearDown(self):
        self.client.close()
        self.backend.close()
        self.tmp.cleanup()

    def test_private_event_roundtrips_json_and_deduplicates(self):
        first = self.client.post('/intake', json=self.event, headers=self.headers)
        second = self.client.post('/intake', json=self.event, headers=self.headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()['thread_id'], 'chat-1')
        self.assertIn('Ghế "đẹp" \\ gỗ', first.json()['reply'])
        listings = self.backend.get('/listings?community_id=demo', headers={'X-API-Key': 'admin-secret'}).json()
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]['seller_id'], 'seller')
        self.assertEqual(listings[0]['title'], 'Ghế "đẹp" \\ gỗ')

    def test_self_and_group_messages_are_ignored(self):
        for patch in ({'is_self': True}, {'thread_type': 'group'}):
            result = self.client.post('/intake', json={**self.event, **patch}, headers=self.headers)
            self.assertTrue(result.json()['ignored'])
            self.assertEqual(result.json()['reply'], '')
        listings = self.backend.get('/listings?community_id=demo', headers={'X-API-Key': 'admin-secret'}).json()
        self.assertEqual(listings, [])

    def test_requires_auth_and_explicit_metadata(self):
        self.assertEqual(self.client.post('/intake', json=self.event).status_code, 401)
        for key in ('message_id', 'sender_id', 'thread_id', 'thread_type', 'is_self'):
            event = dict(self.event)
            del event[key]
            self.assertEqual(self.client.post('/intake', json=event, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.post('/intake', json={**self.event, 'message_id': '  '}, headers=self.headers).status_code, 422)

    def test_backend_422_404_and_409_have_safe_replies(self):
        samples = [('ban Ghế | giá | tốt', 'hợp lệ'), ('xacnhan NM-NOTFOUND', 'không tìm thấy')]
        for i, (message, fragment) in enumerate(samples):
            event = {**self.event, 'message_id': str(i), 'text': message}
            result = self.client.post('/intake', json=event, headers=self.headers).json()
            self.assertIn(fragment, result['reply'].lower())
        first = self.client.post('/intake', json=self.event, headers=self.headers).json()
        listing_id = first['reply'].splitlines()[0].rsplit(' ', 1)[-1].rstrip('.')
        confirm = {**self.event, 'message_id': 'confirm', 'text': f'xacnhan {listing_id}'}
        self.client.post('/intake', json=confirm, headers=self.headers)
        confirm['message_id'] = 'confirm-again'
        self.assertIn('trạng thái', self.client.post('/intake', json=confirm, headers=self.headers).json()['reply'].lower())

    def test_backend_unauthorized_does_not_expose_credentials(self):
        app = create_intake_app('http://backend', 'wrong-secret', 'intake-secret', 'demo', client=self.backend)
        with TestClient(app) as client:
            result = client.post('/intake', json=self.event, headers=self.headers)
            self.assertEqual(result.status_code, 200)
            self.assertNotIn('wrong-secret', result.text)
            self.assertIn('tạm thời', result.json()['reply'].lower())

    def test_invalid_backend_success_response_is_handled_safely(self):
        class MalformedClient:
            def post(self, *args, **kwargs):
                return httpx.Response(200, json={"unexpected": "secret"})
        app = create_intake_app('http://backend', 'backend-secret', 'intake-secret', 'demo', client=MalformedClient())
        with TestClient(app) as client:
            result = client.post('/intake', json=self.event, headers=self.headers)
            self.assertEqual(result.status_code, 200)
            self.assertIn('tạm thời', result.json()['reply'].lower())
            self.assertNotIn('secret', result.text)

    def test_timeout_returns_safe_reply_without_leaking_details(self):
        class TimeoutClient:
            def post(self, *args, **kwargs):
                raise httpx.ReadTimeout('secret and private message')
        app = create_intake_app('http://backend', 'backend-secret', 'intake-secret', 'demo', client=TimeoutClient())
        with TestClient(app) as client:
            result = client.post('/intake', json=self.event, headers=self.headers)
            self.assertEqual(result.status_code, 200)
            self.assertIn('tạm thời', result.json()['reply'].lower())
            self.assertNotIn('secret', result.text)
            self.assertNotIn(self.event['text'], result.text)


if __name__ == '__main__':
    unittest.main()
