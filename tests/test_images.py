import base64
import io
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import httpx
from PIL import Image
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.images import OpenAIModerator, prepare_image, validate_zalo_url


def photo(color='blue'):
    out=io.BytesIO();Image.new('RGB',(24,24),color).save(out,format='PNG')
    return out.getvalue()


class FakeModerator:
    def __init__(self,status='clear'):self.status=status;self.calls=0
    def check(self,data,mime,text):
        self.calls+=1
        return {'status':self.status,'categories':['violence'] if self.status=='flagged' else []}


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.mod=FakeModerator()
        self.client=TestClient(create_app(Path(self.tmp.name)/'test.db','bridge','admin',moderator=self.mod))
        self.admin={'X-API-Key':'admin'};self.n=0
        self.id=self.send('ban Ghế | 500000 | Cũ').json()['listing_id'];self.send('xác nhận')
    def tearDown(self):self.client.close();self.tmp.cleanup()
    def send(self,text):
        self.n+=1
        return self.client.post('/events',headers={'X-API-Key':'bridge'},json=dict(event_id=str(self.n),community_id='demo',sender_id='seller',text=text))
    def upload(self,**patch):
        data=dict(community_id='demo',image_base64=base64.b64encode(photo()).decode());data.update(patch)
        return self.client.post('/listings/'+self.id+'/images',headers=self.admin,json=data)
    def approve(self,**patch):
        body=dict(community_id='demo',action='approve',reason='Đã xem ảnh');body.update(patch)
        row=self.client.get('/listings?community_id=demo',headers=self.admin).json()[0]
        body.setdefault('image_review_token',row.get('image_review_token'))
        return self.client.post('/listings/'+self.id+'/review',headers=self.admin,json=body)

    def test_clear_duplicate_and_protected_image(self):
        first=self.upload();self.assertEqual(first.status_code,200)
        self.assertEqual(first.json()['status'],'clear')
        self.assertEqual(self.upload().json()['image_id'],first.json()['image_id']);self.assertEqual(self.mod.calls,1)
        url='/images/'+first.json()['image_id']
        self.assertEqual(self.client.get(url+'?community_id=other',headers=self.admin).status_code,404)
        self.assertEqual(self.client.get(url+'?community_id=demo').status_code,401)
        self.assertEqual(self.client.get(url+'?community_id=demo',headers=self.admin).headers['content-type'],'image/jpeg')
        self.assertEqual(self.approve().status_code,200)
        self.assertEqual(self.upload().status_code,409)

    def test_flagged_requires_explicit_human_review(self):
        self.mod.status='flagged';self.upload()
        self.assertEqual(self.approve().status_code,409)
        self.assertEqual(self.approve(image_reviewed=True).status_code,200)

    def test_invalid_image_and_wrong_scope(self):
        self.assertEqual(self.upload(image_base64='bad').status_code,422)
        self.assertEqual(self.upload(community_id='other').status_code,404)
        self.assertEqual(self.mod.calls,0)

    def test_url_blocks_non_zalo_and_internal_targets(self):
        for url in ['http://photo.zcdn.me/a','https://127.0.0.1/a','https://evil.com/a','https://photo.zcdn.me.evil.com/a','https://user:pw@photo.zcdn.me/a']:
            with self.assertRaises(ValueError):validate_zalo_url(url)

    def test_provider_uses_moderation_not_chat(self):
        def handle(req):
            self.assertEqual(str(req.url),'https://api.openai.com/v1/moderations')
            self.assertEqual(req.headers['authorization'],'Bearer fake')
            return httpx.Response(200,json={'results':[{'flagged':True,'categories':{'violence':True,'sexual':False}}]})
        result=OpenAIModerator('fake',httpx.MockTransport(handle)).check(photo(),'image/png','Ghế')
        self.assertEqual(result,{'status':'flagged','categories':['violence']})

    def test_normalization_and_unknown_provider_fail_closed(self):
        data,mime,digest=prepare_image(photo())
        self.assertEqual(mime,'image/jpeg');self.assertEqual(len(digest),64)
        result=OpenAIModerator(None).check(data,mime,'test')
        self.assertEqual(result['status'],'unavailable')

    def test_unavailable_service_requires_human_review(self):
        self.mod.status='unavailable';self.upload()
        self.assertEqual(self.approve().status_code,409)
        self.assertEqual(self.approve(image_reviewed=True).status_code,200)

    def test_changed_description_requires_recheck_or_human_review(self):
        import sqlite3
        self.upload()
        # Simulate a seller edit after the moderation snapshot.
        db=sqlite3.connect(Path(self.tmp.name)/'test.db')
        try:
            with db:db.execute('UPDATE listings SET condition=? WHERE id=?',('Nội dung mới',self.id))
        finally:db.close()
        self.assertEqual(self.approve().status_code,409)
        image=self.client.get('/listings?community_id=demo',headers=self.admin).json()[0]['images'][0]
        self.assertEqual(image['status'],'stale')
        self.assertEqual(self.client.post('/images/'+image['id']+'/recheck?community_id=demo',headers=self.admin).status_code,200)
        self.assertEqual(self.approve().status_code,200)

    def test_zalo_image_reuses_current_draft_and_caches_event(self):
        # Use a fresh draft (the setUp listing was already confirmed).
        self.send('ban Bàn | 300000 | Cũ')
        h={'X-API-Key':'bridge','X-Sender-Id':'seller','X-Event-Id':'image-event'}
        with patch('backend.images.fetch_zalo',return_value=photo()) as fetch:
            r=self.client.post('/bridge/zalo-image',headers=h,content=b'NM-IMAGE:\nhttps://photo.zcdn.me/image.jpg')
            self.assertEqual(r.json()['status'],'clear')
            again=self.client.post('/bridge/zalo-image',headers=h,content=b'NM-IMAGE:\nhttps://photo.zcdn.me/image.jpg')
            self.assertEqual(r.json(),again.json());self.assertEqual(fetch.call_count,1)

    def test_dns_private_address_rejected_before_connect(self):
        from backend.images import _fetch_zalo
        with patch('backend.images.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):_fetch_zalo('https://photo.zcdn.me/x')

    def test_review_snapshot_cannot_approve_new_unseen_image(self):
        self.mod.status='flagged';self.upload()
        token=self.client.get('/listings?community_id=demo',headers=self.admin).json()[0]['image_review_token']
        self.upload(image_base64=base64.b64encode(photo('red')).decode())
        self.assertEqual(self.approve(image_reviewed=True,image_review_token=token).status_code,409)
        self.assertEqual(self.approve(image_reviewed=True).status_code,200)
