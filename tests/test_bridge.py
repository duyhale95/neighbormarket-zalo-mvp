import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import create_app


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name)/'test.db', 'bridge', 'admin'))
        self.headers = {'X-API-Key':'bridge', 'X-Sender-Id':'123', 'X-Event-Id':'456', 'Content-Type':'text/plain; charset=utf-8'}
    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()
    def test_raw_text_and_retry(self):
        text = 'ban Ghế "xịn"\nphòng ngủ | 500000 | Cũ, còn tốt'
        r = self.client.post('/bridge/zalo', content=text.encode(), headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'draft')
        again = self.client.post('/bridge/zalo', content=b'changed', headers=self.headers)
        self.assertEqual(again.json(), r.json())
    def test_metadata_auth_and_business_error(self):
        self.assertEqual(self.client.post('/bridge/zalo', content=b'hello').status_code, 401)
        h = dict(self.headers); h.pop('X-Event-Id')
        self.assertEqual(self.client.post('/bridge/zalo', content=b'hello', headers=h).status_code, 422)
        r = self.client.post('/bridge/zalo', content=b'ban bad', headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['business_status'], 422)
        self.assertIn('reply', r.json())
    def test_admin_page_no_embedded_keys(self):
        r = self.client.get('/admin')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('bridge-secret', r.text)

    def test_oversized_whitespace_is_rejected_not_server_error(self):
        r = self.client.post('/bridge/zalo', content=(' ' * 4000 + 'hi').encode(), headers=self.headers)
        self.assertEqual(r.status_code, 422)
