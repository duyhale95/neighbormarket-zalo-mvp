import base64
import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from backend.app import create_app


class GroupImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.client=TestClient(create_app(self.root/'db.sqlite','bridge','admin',group_target={'community_id':'demo','group_id':'12345','group_name':'Demo'}))
        self.admin={'X-API-Key':'admin'};self.bridge={'X-API-Key':'bridge'};self.n=0
        self.id=self.send('ban Ghế | 500000 | Đã dùng').json()['listing_id']
    def tearDown(self):self.client.close();self.tmp.cleanup()
    def send(self,text):
        self.n+=1
        return self.client.post('/events',headers=self.bridge,json=dict(event_id=str(self.n),community_id='demo',sender_id='seller',text=text))
    def photo(self,color):
        out=io.BytesIO();Image.new('RGB',(24,24),color).save(out,format='PNG')
        return self.client.post('/listings/'+self.id+'/images',headers=self.admin,json={'community_id':'demo','image_base64':base64.b64encode(out.getvalue()).decode()}).json()['image_id']
    def approve(self):
        self.send('xác nhận')
        row=self.client.get('/listings?community_id=demo',headers=self.admin).json()[0]
        r=self.client.post('/listings/'+self.id+'/review',headers=self.admin,json=dict(community_id='demo',action='approve',reason='Đã xem ảnh',image_reviewed=True,image_review_token=row['image_review_token']))
        self.assertEqual(r.status_code,200)
    def claim(self,version='2'):
        return self.client.post('/group-publications/claim',headers={**self.bridge,'X-Publisher-Version':version}).json()
    def ack(self,job):
        r=self.client.post('/group-publications/'+job['job_id']+'/ack',headers=self.bridge,json={'token':job['token'],'message_id':'12345'})
        self.assertEqual(r.status_code,200)

    def test_cover_photo_caption_and_all_extra_photos_before_code(self):
        first=self.photo('blue');second=self.photo('red');self.approve()
        self.assertFalse(self.claim('1')['ready'])
        post=self.claim();self.assertEqual(post['part'],'post');self.assertTrue(post['has_image'])
        path=Path(post['image_path']);self.assertTrue(path.is_file());self.assertEqual(path.parent,self.root/'group-media')
        with Image.open(path) as image:self.assertEqual(image.format,'JPEG')
        self.assertIn(self.id,post['message']);self.ack(post)
        extra=self.claim();self.assertTrue(extra['has_image']);self.assertNotEqual(extra['image_path'],post['image_path'])
        self.ack(extra)
        code=self.claim();self.assertEqual(code['part'],'code');self.assertFalse(code['has_image']);self.assertEqual(code['message'],self.id)
        self.ack(code);self.assertFalse(self.claim()['ready'])
        row=self.client.get('/listings?community_id=demo',headers=self.admin).json()[0]
        self.assertEqual(row['publication_status'],'posted')

    def test_no_photo_keeps_legacy_text_publisher_working(self):
        self.approve();job=self.claim('1')
        self.assertTrue(job['ready']);self.assertFalse(job['has_image']);self.assertEqual(job['image_path'],'')

    def test_sold_cancels_extra_images(self):
        self.photo('blue');self.photo('red');self.approve();self.ack(self.claim())
        self.send('daban '+self.id)
        job=self.claim();self.assertEqual(job['part'],'sold');self.assertFalse(job['has_image'])

    def test_uncertain_extra_photo_retry_does_not_repeat_cover(self):
        import sqlite3
        self.photo('blue');self.photo('red');self.approve();self.ack(self.claim());extra=self.claim()
        db=sqlite3.connect(self.root/'db.sqlite')
        try:
            with db:db.execute('UPDATE group_posts SET lease_until=0 WHERE id=?',(extra['job_id'],))
        finally:db.close()
        self.assertFalse(self.claim()['ready'])
        self.client.post('/listings/'+self.id+'/publish',headers=self.admin,json={'community_id':'demo','retry_uncertain':True})
        retry=self.claim();self.assertEqual(retry['part'],extra['part']);self.assertNotEqual(retry['part'],'post')

    def test_old_text_only_post_can_add_images_without_reposting_text(self):
        import sqlite3
        self.photo('blue');self.approve()
        db=sqlite3.connect(self.root/'db.sqlite')
        try:
            with db:
                db.execute("UPDATE group_posts SET image_id=NULL,status='posted',message_id='999' WHERE listing_id=?",(self.id,))
        finally:db.close()
        row=self.client.get('/listings?community_id=demo',headers=self.admin).json()[0]
        self.assertEqual(row['unpublished_image_count'],1)
        self.client.post('/listings/'+self.id+'/publish',headers=self.admin,json={'community_id':'demo'})
        job=self.claim();self.assertTrue(job['has_image']);self.assertNotEqual(job['part'],'post')
        self.ack(job);self.assertFalse(self.claim()['ready'])
