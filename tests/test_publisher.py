import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.channels import MockZaloTransport, SendOutcome
from backend.publisher import Publisher


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name)/'db', 'bridge', 'admin', target_group_id='group'))
        self.bridge = {'X-API-Key':'bridge'}
        self.admin = {'X-API-Key':'admin'}
        self.sequence = 0
        self.transport = MockZaloTransport('303','group')

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def listing(self, action='approve'):
        self.sequence += 1
        event = {'event_id':str(self.sequence), 'community_id':'demo', 'sender_id':'seller',
                 'text':'ban Ghế | 800000 | đã dùng 6 tháng'}
        draft = self.client.post('/events', json=event, headers=self.bridge).json()
        self.client.post('/events', json={**event,'event_id':str(self.sequence)+'c',
                         'text':'xacnhan '+draft['listing_id']}, headers=self.bridge)
        self.client.post('/listings/'+draft['listing_id']+'/review', headers=self.admin,
                         json={'community_id':'demo','action':action,'reason':'QA review'})
        return draft['listing_id']

    def worker(self, client=None, transport=None, group='group'):
        return Publisher(client or self.client, 'bridge', transport or self.transport, group)

    def rows(self):
        return self.client.get('/deliveries?community_id=demo',headers=self.admin).json()

    def test_success_acks_mock_evidence_and_does_not_resend(self):
        self.listing()
        result = self.worker().process_once()
        self.assertEqual(result.status,'sent')
        self.assertTrue(result.simulated)
        self.assertEqual(self.worker().process_once().status,'idle')
        self.assertEqual(len(self.transport.sent),1)
        self.assertEqual(self.rows()[0]['transport_mode'],'mock')
        self.assertNotIn('seller', self.transport.sent[0]['text'])

    def test_unknown_or_missing_receipt_never_retries(self):
        for outcome in (SendOutcome(status='unknown',error='timeout',simulated=True),
                        SendOutcome(status='sent',simulated=True)):
            self.listing()
            class Ambiguous(MockZaloTransport):
                def send_group(self, group_id, text):
                    return outcome
            self.assertEqual(self.worker(transport=Ambiguous('303','group')).process_once().status,'unknown')
            self.assertEqual(self.worker().process_once().status,'idle')
        self.assertTrue(all(row['status']=='unknown' for row in self.rows()))

    def test_definitive_failure_and_allowlist_mismatch(self):
        self.listing()
        class Rejected(MockZaloTransport):
            def send_group(self, group_id, text):
                return SendOutcome(status='not_sent',error='send_rejected',simulated=True)
        self.assertEqual(self.worker(transport=Rejected('303','group')).process_once().status,'failed')
        self.listing()
        self.assertEqual(self.worker(group='other').process_once().status,'failed')
        self.assertEqual(self.transport.sent,[])

    def test_reject_and_sold_are_never_sent(self):
        self.listing('reject')
        lid = self.listing()
        self.client.post('/events', headers=self.bridge, json={'event_id':'sold','sender_id':'seller',
                         'community_id':'demo','text':'daban '+lid})
        self.assertEqual(self.worker().process_once().status,'idle')
        self.assertEqual(self.transport.sent,[])

    def test_ack_lost_after_commit_does_not_send_again(self):
        self.listing()
        real = self.client
        class AckLost:
            def post(self, url, **kwargs):
                response = real.post(url, **kwargs)
                if url.endswith('/sent'):
                    raise httpx.ReadTimeout('do not log raw credentials')
                return response
            def get(self, *args, **kwargs):
                return real.get(*args, **kwargs)
        self.worker(client=AckLost()).process_once()
        self.assertEqual(self.rows()[0]['status'],'sent')
        self.assertEqual(self.worker().process_once().status,'idle')
        self.assertEqual(len(self.transport.sent),1)

    def test_concurrent_claims_only_one_worker_gets_the_job(self):
        self.listing()
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses=list(pool.map(lambda _:self.client.post('/deliveries/claim',headers=self.bridge).status_code,range(4)))
        self.assertEqual(statuses.count(200),1)
        self.assertEqual(statuses.count(204),3)
