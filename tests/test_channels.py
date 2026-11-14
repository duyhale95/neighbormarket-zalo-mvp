import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import create_app
from backend.channels import normalize_deplao
from backend.intake_bridge import create_intake_app


class ChannelTests(unittest.TestCase):
    def raw(self, **updates):
        value = {'msgId': '101', 'fromId': '202', 'threadId': '202', 'threadType': 0,
                 'isSelf': False, 'zaloId': '303', 'content': 'ban Ghế | 800000 | đã dùng 6 tháng',
                 'timestamp': 1730000000000}
        return {**value, **updates}

    def test_normalized_identity_is_stable_account_scoped_and_not_text(self):
        first = normalize_deplao(self.raw(), '303')
        second = normalize_deplao(self.raw(content='sender_id=attacker'), '303')
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(first.sender_id, '202')
        self.assertEqual(first.thread_id, '202')
        self.assertNotEqual(first.event_id, normalize_deplao(self.raw(threadId='404'), '303').event_id)
        self.assertFalse(first.is_self)

    def test_metadata_fails_closed_and_non_text_is_ignored(self):
        for change in ({'msgId': ''}, {'fromId': '202\nX-Key: bad'}, {'isSelf': 'false'},
                       {'threadType': 'bad'}, {'zaloId': 'other'}, {'content': {}}):
            with self.subTest(change=change), self.assertRaises((ValidationError, ValueError)):
                normalize_deplao(self.raw(**change), '303')
        self.assertIsNone(normalize_deplao(self.raw(isSelf=True), '303'))
        self.assertIsNone(normalize_deplao(self.raw(threadType=1), '303'))

    def test_raw_text_intake_preserves_unicode_quotes_and_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(Path(directory)/'db', 'backend', 'admin')) as backend:
                app = create_intake_app('http://backend', 'backend', 'intake', 'demo',
                                        client=backend, account_id='303', allowed_sender_ids={'202'})
                with TestClient(app) as client:
                    headers = {'X-Intake-Key': 'intake', 'Content-Type': 'text/plain; charset=utf-8',
                               'X-Zalo-Account': '303', 'X-Zalo-Sender': '202', 'X-Zalo-Thread': '202',
                               'X-Zalo-Message': '101', 'X-Zalo-Thread-Type': '0', 'X-Zalo-Self': 'false'}
                    text = 'ban Ghế "gỗ" \\ {{ $pageId }} | 800000 | đã dùng\n6 tháng'
                    first = client.post('/intake', headers=headers, content='NM-TEXT:\n'+text)
                    again = client.post('/intake', headers=headers, content='NM-TEXT:\n'+text)
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(first.json(), again.json())
                    self.assertEqual(first.json()['thread_id'], '202')
                    rows = backend.get('/listings?community_id=demo', headers={'X-API-Key':'admin'}).json()
                    self.assertEqual(len(rows), 1)
                    self.assertIn('{{ $pageId }}', rows[0]['title'])
                    self.assertEqual(rows[0]['seller_id'], '202')
                    for patch in ({'X-Zalo-Sender': '999'}, {'X-Zalo-Account':'999'},
                                  {'X-Zalo-Self':''}, {'X-Zalo-Thread-Type':'invalid'}):
                        response = client.post('/intake', headers={**headers, **patch}, content='NM-TEXT:\n'+text)
                        self.assertIn(response.status_code, (403, 422))
                    ignored = client.post('/intake', headers={**headers,'X-Zalo-Self':'true'}, content='NM-TEXT:\n'+text)
                    self.assertTrue(ignored.json()['ignored'])
                    self.assertEqual(client.post('/intake', headers=headers, content='{"sender_id":"999"}').status_code, 422)


if __name__ == '__main__':
    unittest.main()
