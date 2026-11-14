import sqlite3
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import unittest

import test_media_images as fixtures
from test_media_images import photo


class MediaDeliveryTests(unittest.TestCase):
    event=fixtures.MediaImageTests.event
    upload=fixtures.MediaImageTests.upload
    record=fixtures.MediaImageTests.record
    review=fixtures.MediaImageTests.review
    tearDown=fixtures.MediaImageTests.tearDown
    def setUp(self):
        fixtures.MediaImageTests.setUp(self)
        self.client.app.state.publication_mode='photos_v2'

    def approve(self, count=0):
        for color in ('gold','blue','green')[:count]: self.upload(photo(color))
        self.event('ok')
        result=self.review(image_review_token=self.record()['image_review_token'])
        self.assertEqual(result.status_code,200)

    def claim(self, version='2'):
        return self.client.post('/deliveries/claim',headers={**self.bridge,'X-Publisher-Version':version})

    def ack(self, job, receipt='mock-receipt'):
        return self.client.post(f"/deliveries/{job['delivery_id']}/sent",headers=self.bridge,json={
            'claim_token':job['claim_token'],'part_id':job['part_id'],'sent_message_id':receipt,'transport_mode':'mock'})

    def jobs(self): return self.client.get('/deliveries?community_id=demo',headers=self.admin).json()

    def test_cover_additional_code_are_ordered_snapshots_with_independent_receipts(self):
        self.approve(3)
        self.assertEqual(self.claim('1').status_code,204)
        types=[]; receipts=[]
        for index in range(4):
            job=self.claim().json(); types.append(job['part_type'])
            self.assertEqual(self.claim().status_code,204)
            self.assertIn(self.item,job['message'])
            if index<3:
                self.assertTrue(job['has_image']); self.assertTrue(job['image_path'].endswith('.jpg'))
            else: self.assertEqual(job['message'],self.item)
            receipt=f'mock-part-{index}'; receipts.append(receipt)
            self.assertEqual(self.ack(job,receipt).status_code,200)
            self.assertEqual(self.ack(job,receipt).status_code,200)
            self.assertEqual(self.jobs()[0]['status'],'sent' if index==3 else 'queued')
        self.assertEqual(types,['cover_photo_with_caption','additional_photo','additional_photo','listing_code'])
        self.assertEqual([p['sent_message_id'] for p in self.jobs()[0]['parts']],receipts)
        self.assertEqual(self.claim().status_code,204)

    def test_text_then_code_partial_unknown_reconciliation_resumes_without_replay(self):
        self.approve()
        text=self.claim().json(); self.assertEqual(text['part_type'],'post_text'); self.ack(text)
        code=self.claim().json()
        failed=self.client.post(f"/deliveries/{code['delivery_id']}/failure",headers=self.bridge,json={
            'part_id':code['part_id'],'claim_token':code['claim_token'],'outcome':'unknown','error':'timeout','transport_mode':'mock'})
        self.assertEqual(failed.status_code,200); self.assertEqual(self.jobs()[0]['status'],'unknown')
        self.assertEqual(self.claim().status_code,204)
        result=self.client.post(f"/deliveries/{code['delivery_id']}/reconcile",headers=self.admin,json={
            'part_id':code['part_id'],'decision':'sent','reason':'QA: observed receipt of code part','sent_message_id':'mock-observed'})
        self.assertEqual(result.status_code,200); self.assertEqual(self.jobs()[0]['status'],'sent')
        self.assertEqual(self.claim().status_code,204)
        self.assertEqual(self.ack(code).status_code,409)

    def test_sold_cancels_unsent_parts_and_enqueues_one_notice_after_cover_receipt(self):
        self.approve(2)
        cover=self.claim().json(); self.ack(cover)
        sold=self.event(f'daban {self.item}'); self.assertEqual(sold.status_code,200)
        self.assertEqual(self.event(f'daban {self.item}').status_code,409)
        jobs=self.jobs(); parts=jobs[0]['parts']
        self.assertEqual(len([p for p in parts if p['kind']=='sold_notice']),1)
        self.assertTrue(all(p['status']=='cancelled' for p in parts if p['kind'] in ('additional_photo','listing_code')))
        notice=self.claim().json(); self.assertEqual(notice['part_type'],'sold_notice')
        self.assertIn('ĐÃ BÁN',notice['message']); self.ack(notice)
        self.assertEqual(self.event('tìm ghế').json()['listings'],[])
        self.assertEqual(self.claim().status_code,204)

    def test_concurrent_claim_stale_snapshot_and_ambiguous_lease_fail_closed(self):
        self.approve(1)
        with ThreadPoolExecutor(max_workers=2) as pool: responses=list(pool.map(lambda _:self.claim(),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,204])
        job=next(r.json() for r in responses if r.status_code==200)
        self.assertEqual(self.event(f'daban {self.item}').status_code,409)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE delivery_parts SET lease_expires_at=datetime('now','-1 minute') WHERE id=?",(job['part_id'],)); db.commit()
        self.assertEqual(self.claim().status_code,204); self.assertEqual(self.jobs()[0]['status'],'unknown')

    def test_snapshot_tampering_and_private_media_symlink_are_rejected(self):
        self.approve(1)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE listings SET condition='changed after approval' WHERE id=?",(self.item,)); db.commit()
        self.assertEqual(self.claim().status_code,204)
        self.assertEqual(self.jobs()[0]['status'],'failed')
