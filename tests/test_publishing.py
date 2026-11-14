import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import create_app


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db.sqlite'
        self.client=TestClient(create_app(self.path,'bridge','admin',group_target={'community_id':'demo','group_id':'12345','group_name':'Nhóm thử'}))
        self.bridge={'X-API-Key':'bridge'};self.admin={'X-API-Key':'admin'};self.n=0
    def tearDown(self):self.client.close();self.tmp.cleanup()
    def send(self,text):
        self.n+=1
        return self.client.post('/events',headers=self.bridge,json=dict(event_id=str(self.n),community_id='demo',sender_id='seller-private-id',text=text))
    def listing(self):return self.send('ban Ghế | 500000 | Tốt, liên hệ 0912345678 hoặc test@example.com').json()['listing_id']
    def approve(self,id):
        return self.client.post('/listings/'+id+'/review',headers=self.admin,json=dict(community_id='demo',action='approve',reason='Đã kiểm tra'))
    def claim(self):return self.client.post('/group-publications/claim',headers=self.bridge).json()
    def ack(self,job,**patch):
        data=dict(token=job['token'],message_id='98765');data.update(patch)
        return self.client.post('/group-publications/'+job['job_id']+'/ack',headers=self.bridge,json=data)

    def test_approval_queues_two_ordered_parts_and_ack(self):
        id=self.listing()
        self.assertFalse(self.claim()['ready'])
        self.send('xác nhận');self.approve(id)
        self.assertEqual(self.approve(id).status_code,409)
        post=self.claim();self.assertEqual(post['part'],'post');self.assertEqual(post['group_id'],'12345')
        self.assertIn(id,post['message']);self.assertNotIn('seller-private-id',post['message'])
        self.assertNotIn('0912345678',post['message']);self.assertNotIn('test@example.com',post['message'])
        self.assertFalse(self.claim()['ready'])
        self.assertEqual(self.ack(post).status_code,200)
        self.assertEqual(self.ack(post).status_code,200)
        code=self.claim();self.assertEqual(code['part'],'code');self.assertEqual(code['message'],id)
        self.ack(code)
        self.assertFalse(self.claim()['ready'])
        row=self.client.get('/listings?community_id=demo',headers=self.admin).json()[0]
        self.assertEqual(row['publication_status'],'posted')
        self.assertEqual(self.client.post('/listings/'+id+'/publish',headers=self.admin,json={'community_id':'demo'}).json()['publication_status'],'posted')
        self.assertFalse(self.claim()['ready'])

    def test_auth_and_wrong_token(self):
        self.assertEqual(self.client.post('/group-publications/claim').status_code,401)
        self.assertEqual(self.client.post('/group-publications/claim',headers=self.admin).status_code,401)
        id=self.listing();self.send('xác nhận');self.approve(id);job=self.claim()
        self.assertEqual(self.ack(job,token='wrong').status_code,409)
        self.assertEqual(self.ack(job,message_id='').status_code,422)

    def test_expired_lease_requires_manual_review_and_retry(self):
        import sqlite3
        id=self.listing();self.send('xác nhận');self.approve(id);job=self.claim()
        db=sqlite3.connect(self.path)
        try:
            with db:db.execute('UPDATE group_posts SET lease_until=0 WHERE id=?',(job['job_id'],))
        finally:db.close()
        self.assertFalse(self.claim()['ready'])
        row=self.client.get('/listings?community_id=demo',headers=self.admin).json()[0]
        self.assertEqual(row['publication_status'],'uncertain')
        r=self.client.post('/listings/'+id+'/publish',headers=self.admin,json={'community_id':'demo','retry_uncertain':True})
        self.assertEqual(r.status_code,200)
        retry=self.claim();self.assertNotEqual(retry['token'],job['token'])
        self.assertEqual(self.ack(job).status_code,409)

    def test_sold_listing_not_claimed_and_scope_guard(self):
        id=self.listing();self.send('xác nhận');self.approve(id);self.send('daban '+id)
        self.assertFalse(self.claim()['ready'])
        self.assertEqual(self.client.post('/listings/'+id+'/publish',headers=self.admin,json={'community_id':'demo'}).status_code,409)
        self.assertEqual(self.client.post('/listings/'+id+'/publish',headers=self.admin,json={'community_id':'other'}).status_code,404)

    def test_no_target_means_no_publication(self):
        with TestClient(create_app(Path(self.tmp.name)/'disabled.db','bridge','admin')) as client:
            self.assertFalse(client.post('/group-publications/claim',headers=self.bridge).json()['ready'])

    def test_code_retry_does_not_repost_article(self):
        import sqlite3
        id=self.listing();self.send('xác nhận');self.approve(id)
        self.ack(self.claim());code=self.claim()
        db=sqlite3.connect(self.path)
        try:
            with db:db.execute('UPDATE group_posts SET lease_until=0 WHERE id=?',(code['job_id'],))
        finally:db.close()
        self.assertFalse(self.claim()['ready'])
        self.client.post('/listings/'+id+'/publish',headers=self.admin,json={'community_id':'demo','retry_uncertain':True})
        retry=self.claim();self.assertEqual(retry['part'],'code');self.assertEqual(retry['message'],id)

    def test_copy_code_private_lookup_only_shows_approved_available_item(self):
        id=self.listing()
        self.assertEqual(self.send(id).json()['listings'],[])
        self.send('xác nhận');self.approve(id)
        item=self.send(id).json()['listings'][0]
        self.assertEqual(item['id'],id)
        self.assertNotIn('seller_id',item)
        self.assertNotIn('0912345678',item['condition'])
        self.send('daban '+id)
        self.assertEqual(self.send('xem '+id).json()['listings'],[])

    def test_sold_posted_item_queues_one_group_notification(self):
        id=self.listing();self.send('xác nhận');self.approve(id)
        self.ack(self.claim());self.ack(self.claim())
        self.send('daban '+id)
        job=self.claim();self.assertTrue(job['ready']);self.assertEqual(job['part'],'sold')
        self.assertIn('ĐÃ BÁN',job['message']);self.assertIn(id,job['message'])
        self.ack(job);self.assertFalse(self.claim()['ready'])
        self.assertEqual(self.send('daban '+id).status_code,409)

    def test_bare_sold_asks_when_more_than_one_item(self):
        first=self.listing();self.send('xác nhận');self.approve(first)
        second=self.listing();self.send('xác nhận');self.approve(second)
        r=self.send('đã bán').json()
        self.assertIn(first,r['reply']);self.assertIn(second,r['reply'])
        rows=self.client.get('/listings?community_id=demo',headers=self.admin).json()
        self.assertTrue(all(x['status']=='approved' for x in rows))
