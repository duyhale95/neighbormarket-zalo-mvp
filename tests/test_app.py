import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import create_app


class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name) / 'test.db', 'bridge-secret', 'admin-secret'))
        self.bridge = {'X-API-Key': 'bridge-secret'}
        self.admin = {'X-API-Key': 'admin-secret'}
        self.seq = 0

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def event(self, text, user='seller', community='demo', **patch):
        self.seq += 1
        data = dict(event_id=str(self.seq), community_id=community, sender_id=user,
                    text=text, thread_type='private', is_self=False)
        data.update(patch)
        return self.client.post('/events', json=data, headers=self.bridge)

    def listing(self):
        r = self.event('ban Ghế làm việc | 500000 | đã dùng 6 tháng')
        self.assertEqual(r.status_code, 200)
        return r.json()['listing_id']

    def review(self, id, community='demo', action='approve'):
        return self.client.post(f'/listings/{id}/review', headers=self.admin,
                                json=dict(community_id=community, action=action, reason='Đã kiểm tra'))

    def test_full_lifecycle(self):
        id = self.listing()
        self.assertEqual(self.event('tim ghế').json()['listings'], [])
        self.assertEqual(self.review(id).status_code, 409)
        self.assertEqual(self.event(f'xacnhan {id}').json()['status'], 'pending')
        self.assertEqual(self.review(id).json()['status'], 'approved')
        found = self.event('tim ghe').json()['listings']
        self.assertEqual(found[0]['id'], id)
        self.assertNotIn('seller_id', found[0])
        self.assertEqual(self.event(f'daban {id}').json()['status'], 'sold')
        self.assertEqual(self.event('tim ghế').json()['listings'], [])

    def test_tenant_and_owner_boundaries(self):
        id = self.listing()
        self.assertEqual(self.event(f'xacnhan {id}', user='other').status_code, 404)
        self.assertEqual(self.event(f'xacnhan {id}', community='other').status_code, 404)
        self.event(f'xacnhan {id}')
        self.assertEqual(self.review(id, community='other').status_code, 404)
        self.review(id)
        self.assertEqual(self.event('tim ghế', community='other').json()['listings'], [])
        self.assertEqual(self.event(f'daban {id}', user='other').status_code, 404)

    def test_duplicate_event_cached(self):
        first = self.event('ban Ghế | 500 | cũ', event_id='same').json()
        second = self.event('ban Bàn | 700 | mới', event_id='same').json()
        self.assertEqual(first, second)
        rows = self.client.get('/listings?community_id=demo', headers=self.admin).json()
        self.assertEqual(len(rows), 1)

    def test_rejection_not_searchable_and_review_terminal(self):
        id = self.listing()
        self.event(f'xacnhan {id}')
        self.assertEqual(self.review(id, action='reject').json()['status'], 'rejected')
        self.assertEqual(self.review(id).status_code, 409)
        self.assertEqual(self.event('tim ghế').json()['listings'], [])

    def test_bad_inputs_and_ignored_messages(self):
        for text in ['ban Ghế | -1 | cũ', 'ban Ghế | abc | cũ', 'ban Ghế | 100 | ', 'ban Ghế']:
            self.assertEqual(self.event(text).status_code, 422)
        self.assertEqual(self.event('a' * 4001).status_code, 422)
        self.assertTrue(self.event('ban Ghế | 100 | cũ', is_self=True).json()['ignored'])
        self.assertTrue(self.event('ban Ghế | 100 | cũ', thread_type='group').json()['ignored'])
        self.assertEqual(self.client.get('/listings?community_id=demo', headers=self.admin).json(), [])

    def test_separate_auth(self):
        self.assertEqual(self.client.get('/listings?community_id=demo').status_code, 401)
        self.assertEqual(self.client.get('/listings?community_id=demo', headers=self.bridge).status_code, 401)
        data = dict(event_id='x', community_id='demo', sender_id='s', text='hello')
        self.assertEqual(self.client.post('/events', json=data, headers=self.admin).status_code, 401)


if __name__ == '__main__':
    unittest.main()
