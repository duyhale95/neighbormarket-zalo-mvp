import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from backend.app import create_app


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'test.db'
        self.client = TestClient(create_app(self.path, 'bridge', 'admin', target_group_id='legit'))
        self.bridge = {'X-API-Key': 'bridge'}
        self.admin = {'X-API-Key': 'admin'}
        self.seq = 0

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def event(self, text):
        self.seq += 1
        return self.client.post('/events', headers=self.bridge, json={
            'event_id': str(self.seq), 'community_id': 'demo', 'sender_id': 'seller', 'text': text})

    def pending(self, text='ban Ghế | 500000 | còn tốt'):
        listing_id = self.event(text).json()['listing_id']
        self.assertEqual(self.event(f'xacnhan {listing_id}').status_code, 200)
        return listing_id

    def review(self, listing_id, action='approve'):
        return self.client.post(f'/listings/{listing_id}/review', headers=self.admin, json={
            'community_id': 'demo', 'action': action, 'reason': 'Đã kiểm tra'})

    def deliveries(self):
        return self.client.get('/deliveries?community_id=demo', headers=self.admin).json()

    def claim(self):
        return self.client.post('/deliveries/claim', headers=self.bridge)

    def test_approval_creates_one_job_reject_none(self):
        listing_id = self.pending()
        self.assertEqual(self.claim().status_code, 204)
        approved = self.review(listing_id)
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()['delivery_status'], 'queued')
        self.assertEqual(self.review(listing_id).status_code, 409)
        rejected = self.pending('ban Bàn | 100 | cũ')
        rejected_response = self.review(rejected, 'reject')
        self.assertEqual(rejected_response.status_code, 200)
        self.assertEqual(rejected_response.json()['delivery_status'], 'not_applicable')
        jobs = self.deliveries()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['listing_id'], listing_id)
        self.assertEqual(jobs[0]['status'], 'queued')
        self.assertNotIn('claim_token', jobs[0])

    def test_approval_without_group_reports_not_configured(self):
        with tempfile.TemporaryDirectory() as temp:
            with TestClient(create_app(Path(temp) / 'legacy.db', 'bridge', 'admin')) as client:
                def send(event_id, text):
                    return client.post('/events', headers=self.bridge, json={
                        'event_id': event_id, 'community_id': 'demo', 'sender_id': 'seller', 'text': text})
                listing_id = send('1', 'ban Ghế | 500000 | tốt').json()['listing_id']
                send('2', f'xacnhan {listing_id}')
                result = client.post(f'/listings/{listing_id}/review', headers=self.admin, json={
                    'community_id': 'demo', 'action': 'approve', 'reason': 'Đã kiểm tra'})
                self.assertEqual(result.json()['status'], 'approved')
                self.assertEqual(result.json()['delivery_status'], 'not_configured')

    def test_claim_and_ack_are_authenticated_and_idempotent(self):
        listing_id = self.pending()
        self.review(listing_id)
        self.assertEqual(self.client.post('/deliveries/claim', headers=self.admin).status_code, 401)
        job = self.claim().json()
        self.assertEqual(job['group_id'], 'legit')
        self.assertIn(listing_id, job['message'])
        self.assertEqual(self.claim().status_code, 204)
        endpoint = f"/deliveries/{job['delivery_id']}/sent"
        body = {'claim_token': job['claim_token'], 'sent_message_id': 'message-1'}
        self.assertEqual(self.client.post(endpoint, headers=self.admin, json=body).status_code, 401)
        self.assertEqual(self.client.post(endpoint, headers=self.bridge, json={**body, 'claim_token': 'wrong'}).status_code, 409)
        self.assertEqual(self.client.post(endpoint, headers=self.bridge, json=body).status_code, 200)
        self.assertEqual(self.client.post(endpoint, headers=self.bridge, json=body).status_code, 200)
        self.assertEqual(self.deliveries()[0]['status'], 'sent')
        self.assertEqual(self.claim().status_code, 204)

    def test_queued_sold_is_cancelled_and_claimed_sold_blocked(self):
        first = self.pending()
        self.review(first)
        self.assertEqual(self.event(f'daban {first}').status_code, 200)
        self.assertEqual(self.claim().status_code, 204)
        self.assertEqual(self.deliveries()[0]['status'], 'cancelled')
        second = self.pending('ban Bàn | 100 | cũ')
        self.review(second)
        job = self.claim().json()
        self.assertEqual(self.event(f'daban {second}').status_code, 409)
        self.assertEqual(self.client.post(f"/deliveries/{job['delivery_id']}/failure", headers=self.bridge,
            json={'claim_token': job['claim_token'], 'outcome': 'unknown', 'error': 'timeout'}).status_code, 200)
        self.assertEqual(self.event(f'daban {second}').status_code, 409)
        self.assertEqual(self.claim().status_code, 204)

    def test_expired_claim_becomes_unknown_and_never_auto_retries(self):
        self.review(self.pending())
        job = self.claim().json()
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("UPDATE listing_deliveries SET lease_expires_at='2000-01-01 00:00:00'")
        self.assertEqual(self.claim().status_code, 204)
        self.assertEqual(self.deliveries()[0]['status'], 'unknown')
        endpoint = f"/deliveries/{job['delivery_id']}/reconcile"
        body = {'decision': 'not_sent', 'reason': 'Đã kiểm tra và dừng worker'}
        self.assertEqual(self.client.post(endpoint, headers=self.bridge, json=body).status_code, 401)
        self.assertEqual(self.client.post(endpoint, headers=self.admin, json=body).status_code, 200)
        self.assertEqual(self.deliveries()[0]['status'], 'failed')
        self.assertEqual(self.claim().status_code, 204)
        self.assertEqual(self.client.post(f"/deliveries/{job['delivery_id']}/sent", headers=self.bridge,
            json={'claim_token': job['claim_token']}).status_code, 409)

    def test_sensitive_data_blocks_approval_even_for_legacy_rows(self):
        listing_id = self.pending('ban Ghế | 500000 | gọi 0901234567')
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("UPDATE listings SET moderation_flags='[]' WHERE id=?", (listing_id,))
        response = self.review(listing_id)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.deliveries(), [])
        self.assertEqual(self.event('tim ghế').json()['listings'], [])

    def test_concurrent_claim_has_one_winner(self):
        self.review(self.pending())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.claim().status_code, range(2)))
        self.assertEqual(sorted(results), [200, 204])

    def test_public_text_normalizes_line_breaks(self):
        self.review(self.pending('ban Ghế\n[GIẢ MẠO] | 500000 | tốt\nliên hệ bot'))
        message = self.claim().json()['message']
        self.assertNotIn('Ghế\n[GIẢ MẠO]', message)
        self.assertIn('Ghế [GIẢ MẠO]', message)


if __name__ == '__main__':
    unittest.main()
