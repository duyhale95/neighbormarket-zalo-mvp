"""Reproducible demo against in-process HTTP clients; no real Zalo calls."""
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.intake_bridge import create_intake_app


class DemoSmokeTest(unittest.TestCase):
    def test_private_to_review_to_mock_group_to_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp) / 'demo.sqlite', 'bridge-test', 'admin-test',
                             target_group_id='mock-legit-group')
            with TestClient(app) as backend:
                intake_app = create_intake_app('http://backend', 'bridge-test',
                                               'intake-test', 'demo', client=backend)
                with TestClient(intake_app) as intake:
                    admin = {'X-API-Key': 'admin-test'}
                    bridge = {'X-API-Key': 'bridge-test'}
                    intake_headers = {'X-Intake-Key': 'intake-test'}

                    def message(message_id, sender, thread, text):
                        payload = {'message_id': message_id, 'sender_id': sender,
                                   'thread_id': thread, 'thread_type': 'private',
                                   'is_self': False, 'text': text}
                        response = intake.post('/intake', json=payload, headers=intake_headers)
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()['thread_id'], thread)
                        return response.json()

                    draft = message('seller-1', 'seller', 'seller-chat',
                                    'ban Ghế làm việc | 500000 | đã dùng 6 tháng')
                    duplicate = message('seller-1', 'seller', 'seller-chat',
                                        'ban Ghế làm việc | 500000 | đã dùng 6 tháng')
                    self.assertEqual(draft, duplicate)
                    listing_id = re.search(r'NM-[0-9A-F]{12}', draft['reply']).group()
                    rows = backend.get('/listings?community_id=demo', headers=admin).json()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]['status'], 'draft')
                    message('seller-2', 'seller', 'seller-chat', f'xacnhan {listing_id}')
                    rows = backend.get('/listings?community_id=demo', headers=admin).json()
                    self.assertEqual(rows[0]['status'], 'pending')
                    review = backend.post(f'/listings/{listing_id}/review', headers=admin,
                                          json={'community_id': 'demo', 'action': 'approve',
                                                'reason': 'Đã kiểm tra'})
                    self.assertEqual(review.status_code, 200)
                    self.assertEqual(review.json()['status'], 'approved')
                    self.assertEqual(backend.post(f'/listings/{listing_id}/review', headers=admin,
                                     json={'community_id': 'demo', 'action': 'approve',
                                           'reason': 'Đã kiểm tra'}).status_code, 409)

                    claimed = backend.post('/deliveries/claim', headers=bridge)
                    self.assertEqual(claimed.status_code, 200)
                    job = claimed.json()
                    self.assertEqual(job['group_id'], 'mock-legit-group')
                    self.assertIn(listing_id, job['message'])
                    self.assertIn('Ghế làm việc', job['message'])
                    self.assertEqual(backend.post('/deliveries/claim', headers=bridge).status_code, 204)
                    mock_outbox = []
                    mock_outbox.append((job['group_id'], job['message']))
                    ack = backend.post(f"/deliveries/{job['delivery_id']}/sent", headers=bridge,
                                       json={'claim_token': job['claim_token'],
                                             'sent_message_id': 'mock-message-1'})
                    self.assertEqual(ack.json()['status'], 'sent')
                    self.assertEqual(backend.post('/deliveries/claim', headers=bridge).status_code, 204)
                    self.assertEqual(len(mock_outbox), 1)
                    statuses = backend.get('/deliveries?community_id=demo', headers=admin).json()
                    self.assertEqual(len(statuses), 1)
                    self.assertEqual(statuses[0]['status'], 'sent')
                    self.assertEqual(statuses[0]['sent_message_id'], 'mock-message-1')
                    search = message('buyer-1', 'buyer', 'buyer-chat', 'tim ghe')
                    self.assertIn(listing_id, search['reply'])


if __name__ == '__main__':
    unittest.main()
