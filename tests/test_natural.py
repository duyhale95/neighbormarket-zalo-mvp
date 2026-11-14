import json
import tempfile
import unittest
import threading
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.ai_text import ListingPatch, GeminiTextExtractor, AIUnavailable


class Fake:
    def __init__(self): self.calls=[];self.hook=None
    def extract(self,text,previous):
        self.calls.append((text,previous))
        if self.hook: self.hook()
        if text=='fail':raise AIUnavailable('AI tạm thời không khả dụng.')
        if text=='Mình thanh lý ghế 500k':return ListingPatch(intent='sell',title='Ghế làm việc',price_vnd=500000)
        if text=='Dùng 6 tháng, không hỏng':return ListingPatch(intent='sell',condition='Dùng 6 tháng, không hỏng')
        if text=='Đổi giá 450k':return ListingPatch(intent='sell',price_vnd=450000)
        return ListingPatch(intent='other')


class ProviderTests(unittest.TestCase):
    def test_request_and_validated_response(self):
        def handle(req):
            self.assertEqual(req.headers['x-goog-api-key'],'fake-secret')
            body=json.loads(req.content)
            self.assertEqual(body['generationConfig']['responseMimeType'],'application/json')
            self.assertIn('responseJsonSchema',body['generationConfig'])
            output=ListingPatch(intent='sell',title='Ghế',price_vnd=500000).model_dump_json()
            return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':output}]}}]})
        result=GeminiTextExtractor('fake-secret','fake-model',httpx.MockTransport(handle)).extract('bán ghế 500k',{})
        self.assertEqual(result.price_vnd,500000)
        self.assertIsNone(result.condition)

    def test_provider_failures_and_bad_values(self):
        for response in [httpx.Response(401,text='fake-secret'),httpx.Response(200,json={}),
                         httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"intent":"sell","price_vnd":-5}'}]}}]})]:
            with self.subTest(response=response):
                with self.assertRaises(AIUnavailable) as error:
                    GeminiTextExtractor('fake-secret','fake',httpx.MockTransport(lambda r:response)).extract('hello',{})
                self.assertNotIn('fake-secret',str(error.exception))
        for value in [True,'500',-1,1.5]:
            with self.assertRaises(ValueError):ListingPatch(intent='sell',price_vnd=value)

    def test_provider_total_deadline(self):
        gate=threading.Event()
        finished=threading.Event()
        def slow(request):
            gate.wait(2)
            finished.set()
            return httpx.Response(200,json={})
        try:
            with self.assertRaises(AIUnavailable):
                GeminiTextExtractor('fake','fake',httpx.MockTransport(slow),total_timeout=.01).extract('hello',{})
            self.assertFalse(gate.is_set())
            self.assertFalse(finished.is_set())
        finally:gate.set()


class NaturalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.db';self.ai=Fake();self.n=0
        self.client=TestClient(create_app(self.path,'bridge','admin',extractor=self.ai))
    def tearDown(self):self.client.close();self.tmp.cleanup()
    def send(self,text,user='seller',community='demo',**patch):
        self.n+=1
        data=dict(event_id=str(self.n),sender_id=user,community_id=community,text=text);data.update(patch)
        return self.client.post('/events',headers={'X-API-Key':'bridge'},json=data)
    def rows(self):return self.client.get('/listings?community_id=demo',headers={'X-API-Key':'admin'}).json()

    def test_multiturn_persistence_and_explicit_confirmation(self):
        first=self.send('Mình thanh lý ghế 500k').json();id=first['listing_id']
        self.assertEqual(first['missing_fields'],['condition']);self.assertEqual(self.rows(),[])
        self.assertEqual(self.send('xacnhan '+id).status_code,422)
        # Fresh app/process can continue the same persisted draft.
        with TestClient(create_app(self.path,'bridge','admin',extractor=self.ai)) as other:
            r=other.post('/events',headers={'X-API-Key':'bridge'},json=dict(event_id='resume',sender_id='seller',community_id='demo',text='Dùng 6 tháng, không hỏng'))
        self.assertEqual(r.json()['listing_id'],id)
        self.assertEqual(self.rows()[0]['status'],'draft')
        self.assertEqual(self.send('Đổi giá 450k').json()['listing_id'],id)
        self.assertEqual(self.rows()[0]['price_vnd'],450000)
        self.assertEqual(self.send('xacnhan '+id).json()['status'],'pending')
        self.assertEqual(self.send('tim ghế').json()['listings'],[])
        self.client.post('/listings/'+id+'/review',headers={'X-API-Key':'admin'},json=dict(community_id='demo',action='approve',reason='Kiểm tra'))
        self.assertEqual(self.send('tim ghế').json()['listings'][0]['id'],id)

    def test_duplicate_isolation_and_ignored_events(self):
        first=self.send('Mình thanh lý ghế 500k',event_id='duplicate').json()
        self.assertEqual(self.send('Dùng 6 tháng, không hỏng',event_id='duplicate').json(),first)
        self.assertEqual(len(self.ai.calls),1)
        self.send('Dùng 6 tháng, không hỏng',user='other')
        self.assertEqual(self.ai.calls[-1][1],{})
        self.send('Dùng 6 tháng, không hỏng',community='other')
        self.assertEqual(self.ai.calls[-1][1],{})
        self.send('hello',is_self=True)
        self.assertEqual(len(self.ai.calls),3)

    def test_cancel_and_confirmed_listing_not_modified(self):
        id=self.send('Mình thanh lý ghế 500k').json()['listing_id']
        self.send('Dùng 6 tháng, không hỏng')
        self.send('huy nhap')
        self.assertEqual(self.send('xacnhan '+id).status_code,409)
        second=self.send('Mình thanh lý ghế 500k').json()['listing_id']
        self.assertNotEqual(second,id)
        self.send('Dùng 6 tháng, không hỏng');self.send('xacnhan '+second)
        self.send('Đổi giá 450k')
        self.assertEqual(next(r for r in self.rows() if r['id']==second)['price_vnd'],500000)

    def test_error_other_and_bridge(self):
        self.assertEqual(self.send('fail').status_code,503)
        self.assertEqual(self.rows(),[])
        self.assertNotIn('listing_id',self.send('hello').json())
        r=self.client.post('/bridge/zalo',headers={'X-API-Key':'bridge','X-Sender-Id':'seller','X-Event-Id':'bridge1'},content='NM-TEXT:\nMình thanh lý ghế 500k'.encode())
        self.assertIn('condition',r.json()['missing_fields'])

    def test_revision_change_during_ai_does_not_overwrite(self):
        id=self.send('Mình thanh lý ghế 500k').json()['listing_id']
        self.send('Dùng 6 tháng, không hỏng')
        self.ai.hook=lambda:self.send('xacnhan '+id)
        self.assertEqual(self.send('Đổi giá 450k').status_code,409)
        self.assertEqual(self.rows()[0]['status'],'pending')
        self.assertEqual(self.rows()[0]['price_vnd'],500000)

    def test_legacy_new_listing_clears_natural_context(self):
        self.send('Mình thanh lý ghế 500k')
        self.send('ban Bàn | 700000 | Mới')
        self.send('Dùng 6 tháng, không hỏng')
        self.assertEqual(self.ai.calls[-1][1],{})

    def test_overlapping_natural_message_is_rejected_without_second_ai_call(self):
        responses=[]
        self.ai.hook=lambda:responses.append(self.send('Đổi giá 450k'))
        self.send('Mình thanh lý ghế 500k')
        self.assertEqual(responses[0].status_code,409)
        self.assertEqual(len(self.ai.calls),1)

    def test_first_turn_cancel_invalidates_inflight_creation(self):
        self.ai.hook=lambda:self.send('huy nhap')
        self.assertEqual(self.send('Mình thanh lý ghế 500k').status_code,409)
        self.assertEqual(self.rows(),[])

    def test_first_turn_legacy_listing_invalidates_inflight_creation(self):
        self.ai.hook=lambda:self.send('ban Bàn | 700000 | Mới')
        self.assertEqual(self.send('Mình thanh lý ghế 500k').status_code,409)
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(self.rows()[0]['title'],'Bàn')

    def test_bare_confirmation_uses_current_draft_without_model(self):
        id=self.send('Mình thanh lý ghế 500k').json()['listing_id']
        self.assertEqual(self.send('xác nhận').status_code,422)
        self.send('Dùng 6 tháng, không hỏng')
        count=len(self.ai.calls)
        result=self.send('  Xác   nhận  ',event_id='confirm-current').json()
        self.assertEqual(result['listing_id'],id)
        self.assertEqual(result['status'],'pending')
        self.assertEqual(len(self.ai.calls),count)
        self.assertEqual(self.send('xác nhận',event_id='confirm-current').json(),result)
        self.assertEqual(self.send('xác nhận').status_code,409)

    def test_current_pointer_is_scoped_and_structured_listings_work(self):
        id=self.send('ban Ghế | 500000 | Cũ').json()['listing_id']
        self.assertEqual(self.send('xác nhận',user='other').status_code,409)
        self.assertEqual(self.send('xác nhận',community='other').status_code,409)
        self.assertEqual(self.send('xac nhan').json()['listing_id'],id)

    def test_bare_confirmation_does_not_pick_older_draft(self):
        old=self.send('ban Ghế cũ | 500000 | Cũ').json()['listing_id']
        latest=self.send('ban Bàn | 700000 | Mới').json()['listing_id']
        self.assertEqual(self.send('xác nhận').json()['listing_id'],latest)
        self.assertEqual(self.send('xác nhận').status_code,409)
        self.assertEqual(next(r for r in self.rows() if r['id']==old)['status'],'draft')
        self.assertEqual(self.send('xác nhận '+old).json()['listing_id'],old)
