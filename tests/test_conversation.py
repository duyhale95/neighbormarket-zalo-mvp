import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.vnd import parse_vnd


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'db'
        self.client=TestClient(create_app(self.path,'bridge','admin',target_group_id='group'))
        self.seq=0

    def tearDown(self):
        self.client.close(); self.tmp.cleanup()

    def event(self,text,sender='seller',community='demo',event_id=None):
        self.seq+=1
        return self.client.post('/events',headers={'X-API-Key':'bridge'},json={
            'event_id':event_id or str(self.seq),'sender_id':sender,'community_id':community,
            'text':text,'source_channel':'mock'})

    def rows(self):
        return self.client.get('/listings?community_id=demo',headers={'X-API-Key':'admin'}).json()

    def test_vnd_parser_does_not_guess_ambiguous_values(self):
        for text,price in [('800k',800000),('1tr2',1200000),('1 triệu 5',1500000),
                           ('1.200.000',1200000),('0',None),('800',None),('6 tháng',None),
                           ('-800k',None),('1,5tr2',None)]:
            with self.subTest(text=text): self.assertEqual(parse_vnd(text),price)

    def test_natural_message_draft_edit_confirm_and_legacy_search(self):
        with patch.dict('os.environ',{'AI_ENABLED':'false'}):
            first=self.event('Mình muốn thanh lý chiếc ghế công thái học, dùng 6 tháng, giá 800k.',event_id='same').json()
            again=self.event('Mình muốn thanh lý chiếc ghế công thái học, dùng 6 tháng, giá 800k.',event_id='same').json()
        self.assertEqual(first,again)
        self.assertEqual(first['status'],'draft')
        self.assertEqual(self.rows()[0]['price_vnd'],800000)
        self.assertEqual(self.rows()[0]['title'],'ghế công thái học')
        self.assertEqual(self.event('sửa giá 700k').json()['listing_id'],first['listing_id'])
        self.event('sửa tiêu đề Ghế xoay')
        self.assertEqual(len(self.rows()),1)
        self.assertEqual(self.rows()[0]['title'],'Ghế xoay')
        self.assertEqual(self.rows()[0]['price_vnd'],700000)
        self.assertEqual(self.event('ok').json()['status'],'pending')
        self.assertEqual(self.event('sửa giá 500k').status_code,409)
        self.assertEqual(self.event('tim ghế').json()['listings'],[])

    def test_clarification_survives_restart_and_is_sender_scoped(self):
        result=self.event('Mình muốn bán chiếc bàn học gỗ.').json()
        self.assertEqual(result['status'],'incomplete')
        self.assertIn('giá',result['reply'])
        self.assertEqual(self.rows(),[])
        self.assertEqual(self.event('ok').status_code,409)
        self.assertEqual(self.event('800k',sender='other').json().get('status'),None)
        self.assertEqual(self.event('800k',community='other').json().get('status'),None)
        self.client.close()
        self.client=TestClient(create_app(self.path,'bridge','admin',target_group_id='group'))
        self.event('giá 800k')
        complete=self.event('Đã dùng 6 tháng, còn tốt.').json()
        self.assertEqual(complete['status'],'draft')
        self.assertEqual(self.rows()[0]['title'],'bàn học gỗ')
        self.assertEqual(self.rows()[0]['price_vnd'],800000)

    def test_cancel_does_not_delete_and_owner_cannot_edit_confirm_other_listing(self):
        draft=self.event('ban Ghế | 800000 | cũ').json()['listing_id']
        self.assertEqual(self.event('hủy '+draft,sender='other').status_code,404)
        self.assertEqual(self.event('hủy').json()['status'],'cancelled')
        self.assertEqual(self.rows()[0]['status'],'cancelled')
        self.assertEqual(self.event('xacnhan '+draft).status_code,409)
        self.assertEqual(self.event('sửa tiêu đề Bàn').status_code,409)
        self.assertEqual(self.event('ok',sender='other').status_code,409)

    def test_late_ai_result_does_not_resurrect_cancelled_context_or_hold_write_lock(self):
        entered=threading.Event(); release=threading.Event()
        def slow(text):
            entered.set(); release.wait(3)
            return {'intent':'sell','title':'Ghế','price_vnd':800000,'condition':'cũ',
                    'missing_fields':[],'risk_flags':[]}
        self.event('Mình muốn bán chiếc ghế.')
        with patch('backend.app.extract_listing',side_effect=slow), patch.dict('os.environ',{'AI_ENABLED':'true','OPENAI_API_KEY':'fake'}):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(self.event,'Giá 800k, cũ')
                self.assertTrue(entered.wait(2))
                try:
                    cancelled=self.event('hủy')
                    self.assertEqual(cancelled.status_code,200)
                finally: release.set()
                self.assertEqual(future.result().status_code,409)
        self.assertEqual(self.rows(),[])

    def test_model_timeout_uses_bounded_fallback_without_confirming(self):
        with patch('backend.app.extract_listing',side_effect=httpx.ReadTimeout('private-key')), patch.dict(
                'os.environ',{'AI_ENABLED':'true','OPENAI_API_KEY':'fake'}):
            response=self.event('Mình muốn bán chiếc ghế, giá 800k, dùng 6 tháng.').json()
        self.assertEqual(response['status'],'draft')
        self.assertNotIn('private-key',str(response))
        self.assertEqual(self.rows()[0]['moderation']['ai_status'],'unavailable')
        self.assertEqual(self.client.post('/deliveries/claim',headers={'X-API-Key':'bridge'}).status_code,204)
