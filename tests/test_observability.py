import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from backend.app import create_app


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name) / 'db.sqlite', 'bridge-secret', 'admin-secret', target_group_id='group'))
        self.bridge = {'X-API-Key': 'bridge-secret'}
        self.admin = {'X-API-Key': 'admin-secret'}

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def event(self, event_id, text, community='demo'):
        return self.client.post('/events', headers=self.bridge, json={'event_id': event_id,
            'community_id': community, 'sender_id': 'seller', 'text': text})

    def test_stats_are_scoped_and_admin_only(self):
        self.assertEqual(self.client.get('/stats?community_id=demo', headers=self.bridge).status_code, 401)
        draft = self.event('1', 'ban Ghế | 500000 | cũ').json()['listing_id']
        pending = self.event('2', 'ban Bàn | 100000 | mới').json()['listing_id']
        self.event('3', f'xacnhan {pending}')
        self.event('4', 'ban Đèn | 50000 | tốt', community='other')
        stats = self.client.get('/stats?community_id=demo', headers=self.admin).json()
        self.assertEqual(stats, {'total': 2, 'pending': 1, 'approved': 0, 'rejected': 0, 'sold': 0, 'sent': 0})
        self.assertTrue(draft)

    def test_structured_audit_links_lifecycle_without_raw_data_or_tokens(self):
        secret_content = 'Tên riêng tư XYZ'
        with self.assertLogs('neighbormarket.audit', level='INFO') as logs:
            event_id = '0901234567-private-token'
            listing = self.event(event_id, f'ban {secret_content} | 500 | cũ').json()['listing_id']
            self.event('event-b', f'xacnhan {listing}')
            review = self.client.post(f'/listings/{listing}/review', headers=self.admin,
                json={'community_id': 'demo', 'action': 'approve', 'reason': 'lý do riêng tư'})
            self.assertEqual(review.status_code, 200)
            job = self.client.post('/deliveries/claim', headers=self.bridge).json()
            failure = self.client.post(f"/deliveries/{job['delivery_id']}/failure", headers=self.bridge,
                json={'claim_token': job['claim_token'], 'outcome': 'unknown', 'error': 'secret-error-value'})
            self.assertEqual(failure.status_code, 200)
        records = [json.loads(record.getMessage()) for record in logs.records]
        digest = hashlib.sha256(event_id.encode('utf-8')).hexdigest()
        self.assertTrue(any(row.get('event_id') == digest and row.get('correlation_id') == digest
                            and row.get('listing_id') == listing for row in records))
        self.assertTrue(any(row.get('actor') == 'admin-key' and row.get('listing_id') == listing for row in records))
        self.assertTrue(any(row.get('delivery_id') == job['delivery_id'] and row.get('delivery_status') == 'unknown' for row in records))
        output = json.dumps(records, ensure_ascii=False)
        for private in (event_id, secret_content, 'lý do riêng tư', 'bridge-secret', 'admin-secret', 'secret-error-value', job['claim_token']):
            self.assertNotIn(private, output)


if __name__ == '__main__':
    unittest.main()
