"""Security, concurrency and partial-failure regressions for images and delivery parts.

Synthetic data only. Moderator, CDN and transport are local stubs; no network.
"""
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import test_media_images as fixtures
from backend.app import create_app
from test_media_images import photo


class Regressions(unittest.TestCase):
    event = fixtures.MediaImageTests.event
    upload = fixtures.MediaImageTests.upload
    record = fixtures.MediaImageTests.record
    review = fixtures.MediaImageTests.review
    tearDown = fixtures.MediaImageTests.tearDown

    def setUp(self):
        fixtures.MediaImageTests.setUp(self)

    def photos_v2(self):
        self.client.app.state.publication_mode = 'photos_v2'

    def approve(self, count=0, item=None, sender='seller'):
        item = item or self.item
        for color in ('gold', 'blue', 'green')[:count]:
            self.upload(photo(color), item=item)
        self.event('ok', sender=sender)
        token = next(r for r in self.client.get('/listings?community_id=demo', headers=self.admin).json()
                     if r['id'] == item)['image_review_token']
        result = self.client.post(f'/listings/{item}/review', headers=self.admin, json={
            'community_id': 'demo', 'action': 'approve', 'reason': 'QA tổng hợp', 'image_review_token': token})
        self.assertEqual(result.status_code, 200, result.text)

    def claim(self, version='2'):
        return self.client.post('/deliveries/claim', headers={**self.bridge, 'X-Publisher-Version': version})

    def ack(self, job, receipt='mock-receipt', part_id=None, mode='mock'):
        body = {'claim_token': job['claim_token'], 'sent_message_id': receipt, 'transport_mode': mode}
        if part_id or job.get('part_id'):
            body['part_id'] = part_id or job['part_id']
        return self.client.post(f"/deliveries/{job['delivery_id']}/sent", headers=self.bridge, json=body)

    def fail(self, job, outcome):
        return self.client.post(f"/deliveries/{job['delivery_id']}/failure", headers=self.bridge, json={
            'claim_token': job['claim_token'], 'part_id': job['part_id'], 'outcome': outcome,
            'error': 'timeout' if outcome == 'unknown' else 'send_rejected', 'transport_mode': 'mock'})

    def reconcile(self, delivery_id, **body):
        return self.client.post(f'/deliveries/{delivery_id}/reconcile', headers=self.admin,
                                json={'reason': 'QA: kiểm tra receipt giả lập', **body})

    def jobs(self):
        return {r['listing_id']: r for r in self.client.get('/deliveries?community_id=demo', headers=self.admin).json()}

    def expire(self, part_id):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE delivery_parts SET lease_expires_at=datetime('now','-1 minute') WHERE id=?", (part_id,))
            db.commit()

    # --- publisher compatibility -------------------------------------------------------

    def test_v1_publisher_is_not_blocked_by_a_parent_that_gained_parts(self):
        self.approve()
        job = self.claim('1').json()
        self.assertNotIn('part_id', job)
        self.assertEqual(self.ack(job, 'mock-legacy').status_code, 200)
        self.assertEqual(self.event(f'daban {self.item}').status_code, 200)
        second = self.event('ban Bàn | 900000 | mới', sender='other').json()['listing_id']
        self.approve(item=second, sender='other')
        legacy = self.claim('1')
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.json()['delivery_id'], self.jobs()[second]['id'])
        self.assertEqual(self.ack(legacy.json(), 'mock-legacy-2').status_code, 200)
        notice = self.claim('2').json()
        self.assertEqual(notice['part_type'], 'sold_notice')
        self.assertEqual(self.jobs()[self.item]['parts'][0]['sent_message_id'], 'mock-legacy')

    def test_rules_tightened_after_approval_block_v1_v2_and_photo_publication(self):
        for mode, version, count in (('single', '2', 0), ('photos_v2', '2', 1), ('single', '1', 0)):
            with self.subTest(mode=mode, version=version):
                self.client.app.state.publication_mode = mode
                item = self.event(f'ban Món {mode}{version} | 500000 | còn tốt', sender=mode + version).json()['listing_id']
                self.approve(count, item=item, sender=mode + version)
                with patch('backend.app.moderation_flags', return_value=['sensitive_information']):
                    self.assertEqual(self.claim(version).status_code, 204)
                job = self.jobs()[item]
                self.assertEqual((job['status'], job['last_error']), ('failed', 'sensitive_information'))
                self.assertTrue(all(p['status'] == 'failed' for p in job['parts']))
                self.assertEqual(self.claim(version).status_code, 204)

    def test_late_v1_ack_retry_after_sold_is_replayed_not_rejected(self):
        self.approve()
        job = self.claim('1').json()
        self.assertEqual(self.ack(job, 'mock-legacy').status_code, 200)
        self.assertEqual(self.event(f'daban {self.item}').status_code, 200)
        self.assertEqual(self.ack(job, 'mock-legacy').status_code, 200)
        self.assertEqual(self.ack(job, 'mock-other').status_code, 409)
        self.assertEqual(self.claim('2').json()['part_type'], 'sold_notice')

    def test_part_ack_needs_explicit_receipt_and_matching_part(self):
        self.photos_v2(); self.approve(2)
        cover = self.claim().json()
        self.assertEqual(self.ack(cover, mode='unverified').status_code, 422)
        self.assertEqual(self.ack(cover, part_id='0' * 32).status_code, 409)
        self.assertEqual(self.ack(cover, 'mock-cover').status_code, 200)
        self.assertEqual(self.ack(cover, 'mock-cover').status_code, 200)
        self.assertEqual(self.ack(cover, 'mock-different').status_code, 409)
        extra = self.claim().json()
        self.assertEqual(self.ack(extra, part_id=cover['part_id']).status_code, 409)
        parts = self.jobs()[self.item]['parts']
        self.assertEqual([p['sent_message_id'] for p in parts[:2]], ['mock-cover', None])

    # --- partial failure / lost ACK -----------------------------------------------------

    def test_lost_cover_ack_becomes_unknown_then_late_ack_resumes_only_next_part(self):
        self.photos_v2(); self.approve(2)
        cover = self.claim().json()
        self.expire(cover['part_id'])
        self.assertEqual(self.claim().status_code, 204)
        self.assertEqual(self.jobs()[self.item]['status'], 'unknown')
        self.assertEqual(self.event(f'daban {self.item}').status_code, 409)
        self.assertEqual(self.ack(cover, 'mock-late').status_code, 200)
        nxt = self.claim().json()
        self.assertEqual(nxt['part_type'], 'additional_photo')
        cover_row = self.jobs()[self.item]['parts'][0]
        self.assertEqual((cover_row['status'], cover_row['attempts']), ('sent', 1))

    def test_multipart_reconcile_requires_the_unknown_part_and_evidence(self):
        self.photos_v2(); self.approve(2)
        cover = self.claim().json()
        self.assertEqual(self.fail(cover, 'unknown').status_code, 200)
        delivery = cover['delivery_id']
        self.assertEqual(self.reconcile(delivery, decision='sent', sent_message_id='mock-seen').status_code, 422)
        self.assertEqual(self.reconcile(delivery, decision='sent', sent_message_id='mock-seen', part_id='f' * 32).status_code, 409)
        self.assertEqual(self.reconcile(delivery, decision='sent', part_id=cover['part_id']).status_code, 422)
        ok = self.reconcile(delivery, decision='sent', sent_message_id='mock-seen', part_id=cover['part_id'])
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['status'], 'queued')
        self.assertEqual(self.ack(cover, 'mock-seen').status_code, 409)
        nxt = self.claim().json()
        self.assertEqual(nxt['part_type'], 'additional_photo')
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT part_id FROM delivery_reconciliations').fetchone()[0], cover['part_id'])

    def test_reconcile_not_sent_and_definitive_failure_block_remaining_parts(self):
        self.photos_v2(); self.approve(2)
        cover = self.claim().json()
        self.assertEqual(self.fail(cover, 'not_sent').status_code, 200)
        self.assertEqual(self.jobs()[self.item]['status'], 'failed')
        self.assertEqual(self.claim().status_code, 204)
        self.assertEqual(self.reconcile(cover['delivery_id'], decision='not_sent', part_id=cover['part_id']).status_code, 409)
        self.assertEqual(self.event(f'daban {self.item}').status_code, 200)
        parts = self.jobs()[self.item]['parts']
        self.assertFalse([p for p in parts if p['kind'] == 'sold_notice'])
        self.assertTrue(all(p['status'] == 'cancelled' for p in parts))
        self.assertEqual(self.claim().status_code, 204)

    def test_failure_after_cover_receipt_still_allows_one_sold_notice(self):
        self.photos_v2(); self.approve(2)
        self.ack(self.claim().json(), 'mock-cover')
        extra = self.claim().json()
        self.fail(extra, 'not_sent')
        self.assertEqual(self.event(f'daban {self.item}').status_code, 200)
        notice = self.claim().json()
        self.assertEqual(notice['part_type'], 'sold_notice')
        self.assertEqual(self.ack(notice, 'mock-sold').status_code, 200)
        self.assertEqual(self.claim().status_code, 204)
        parts = self.jobs()[self.item]['parts']
        self.assertEqual([(p['kind'], p['status']) for p in parts], [
            ('cover_photo_with_caption', 'sent'), ('additional_photo', 'cancelled'),
            ('listing_code', 'cancelled'), ('sold_notice', 'sent')])
        self.assertEqual(parts[0]['sent_message_id'], 'mock-cover')

    # --- snapshots and private export ---------------------------------------------------

    def test_image_bytes_changed_after_approval_fail_closed(self):
        self.photos_v2(); self.approve(1)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE listing_images SET data=? WHERE listing_id=?', (b'tampered', self.item)); db.commit()
        self.assertEqual(self.claim().status_code, 204)
        job = self.jobs()[self.item]
        self.assertEqual((job['status'], job['parts'][0]['last_error']), ('failed', 'unsafe_media'))

    def test_exported_file_changed_on_disk_is_not_sent(self):
        self.photos_v2(); self.approve(1)
        cover = self.claim().json()
        Path(cover['image_path']).write_bytes(b'replaced')
        self.expire(cover['part_id'])
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE delivery_parts SET status='queued' WHERE id=?", (cover['part_id'],))
            db.execute("UPDATE listing_deliveries SET status='queued'"); db.commit()
        self.assertEqual(self.claim().status_code, 204)
        self.assertEqual(self.jobs()[self.item]['parts'][0]['last_error'], 'unsafe_media')

    def test_media_directory_must_stay_inside_private_database_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            for media in (Path(temp) / '..' / 'escape', Path(temp).parent):
                with self.assertRaises(ValueError):
                    create_app(Path(temp) / 'private' / 'db.sqlite', 'b', 'a', media_dir=media)

    def test_symlinked_export_path_is_rejected(self):
        self.photos_v2(); self.approve(1)
        part = self.jobs()[self.item]['parts'][0]['id']
        media = self.path.parent / 'group-media'; media.mkdir(exist_ok=True)
        outside = Path(self.temp.name).parent / f'nm-outside-{part}.jpg'
        try:
            os.symlink(outside, media / f'{part}.jpg')
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation not permitted on this host')
        try:
            self.assertEqual(self.claim().status_code, 204)
            self.assertEqual(self.jobs()[self.item]['parts'][0]['last_error'], 'unsafe_media')
            self.assertFalse(outside.exists())
        finally:
            (media / f'{part}.jpg').unlink(missing_ok=True)

    def test_media_directory_redirected_outside_private_root_is_rejected(self):
        self.photos_v2(); self.approve(1)
        outside = Path(tempfile.mkdtemp(prefix='nm-outside-'))
        media = self.path.parent / 'group-media'
        try:
            if os.name == 'nt':
                import _winapi
                _winapi.CreateJunction(str(outside), str(media))
            else:
                os.symlink(outside, media, target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest('directory link not permitted on this host')
        try:
            self.assertEqual(self.claim().status_code, 204)
            self.assertEqual(self.jobs()[self.item]['parts'][0]['last_error'], 'unsafe_media')
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            os.rmdir(media) if os.name == 'nt' else media.unlink()
            outside.rmdir()

    # --- image concurrency and transactions ---------------------------------------------

    def test_late_moderation_result_cannot_overwrite_a_newer_recheck(self):
        release = threading.Event(); started = threading.Event()

        class Slow:
            calls = 0
            def check(inner, data, mime, text):
                inner.calls += 1
                if inner.calls == 1:
                    started.set(); release.wait(10)
                    return {'status': 'clear', 'categories': [], 'model': 'late'}
                return {'status': 'flagged', 'categories': ['violence'], 'model': 'recheck'}

        self.client.app.state.images.moderator = Slow()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.upload)
            self.assertTrue(started.wait(10))
            image = self.record()['images'][0]
            self.assertEqual(image['status'], 'pending')
            recheck = f"/images/{image['id']}/recheck?community_id=demo"
            self.assertEqual(self.client.post(recheck, headers=self.admin).status_code, 409)
            with closing(sqlite3.connect(self.path)) as db:
                db.execute('UPDATE listing_images SET updated_at=updated_at-120'); db.commit()
            self.assertEqual(self.client.post(recheck, headers=self.admin).json()['status'], 'flagged')
            release.set(); self.assertEqual(pending.result().status_code, 200)
        final = self.record()['images'][0]
        self.assertEqual((final['status'], final['model']), ('flagged', 'recheck'))
        self.assertNotEqual(final['revision'], image['revision'])

    def test_model_call_runs_outside_sqlite_write_transaction(self):
        path = self.path; observed = []

        class Probe:
            def check(inner, data, mime, text):
                with closing(sqlite3.connect(path, timeout=0)) as db:
                    db.execute('BEGIN IMMEDIATE'); db.rollback()
                observed.append(True)
                return {'status': 'clear', 'categories': [], 'model': 'probe'}

        self.client.app.state.images.moderator = Probe()
        image = self.upload().json()['image_id']
        self.assertEqual(self.client.post(f'/images/{image}/recheck?community_id=demo', headers=self.admin).status_code, 200)
        self.assertEqual(observed, [True, True])

    def test_concurrent_distinct_uploads_respect_five_image_limit(self):
        colors = [(i * 30, 40, 90) for i in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            codes = list(pool.map(lambda c: self.upload(photo(c)).status_code, colors))
        self.assertEqual(sorted(codes), [200] * 5 + [409] * 3)
        self.assertEqual(len(self.record()['images']), 5)

    def test_duplicate_concurrent_image_events_store_one_image(self):
        store = self.client.app.state.images
        with patch('backend.images.fetch_zalo', return_value=photo('teal')):
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: store.receive_zalo('https://photo-zalo.zadn.vn/x.jpg', 'demo', 'seller', 'same'), range(4)))
        self.assertEqual(len({r['image_id'] for r in results}), 1)
        self.assertEqual(len(self.record()['images']), 1)

    def test_image_attached_to_draft_is_rejected_once_seller_confirms_during_fetch(self):
        store = self.client.app.state.images
        def confirm_while_downloading(url):
            self.event('ok'); return photo('olive')
        with patch('backend.images.fetch_zalo', side_effect=confirm_while_downloading):
            with self.assertRaises(Exception):
                store.receive_zalo('https://photo-zalo.zadn.vn/x.jpg', 'demo', 'seller', 'late')
        self.assertEqual(self.record()['images'], [])
        self.assertEqual(self.record()['status'], 'pending')


class SupplementalPhotoLimit(unittest.TestCase):
    """Photos after confirmation are refused with an explicit reply, never attached silently."""

    def test_photo_after_confirmation_gets_explicit_refusal(self):
        from backend.intake_bridge import create_intake_app
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(
                Path(temp) / 'db.sqlite', 'bridge', 'admin', image_moderator=fixtures.Moderator(),
                zalo_images_enabled=True)) as backend:
            def event(event_id, text):
                backend.post('/events', headers={'X-API-Key': 'bridge'}, json={
                    'event_id': event_id, 'community_id': 'demo', 'sender_id': '202', 'text': text}).raise_for_status()
            event('d1', 'ban Ghế | 500000 | còn tốt'); event('d2', 'ok')
            with TestClient(create_intake_app('http://backend', 'bridge', 'intake', 'demo', client=backend,
                                              account_id='303', allowed_sender_ids={'202'}, images_enabled=True)) as adapter:
                headers = {'X-Intake-Key': 'intake', 'Content-Type': 'text/plain', 'X-Zalo-Account': '303',
                           'X-Zalo-Sender': '202', 'X-Zalo-Thread': '202', 'X-Zalo-Message': '9',
                           'X-Zalo-Thread-Type': '0', 'X-Zalo-Self': 'false'}
                with patch('backend.images.fetch_zalo', return_value=photo()) as fetch:
                    reply = adapter.post('/intake/image', headers=headers,
                                         content='NM-IMAGE:\nhttps://photo-zalo.zadn.vn/a.jpg').json()['reply']
                    fetch.assert_not_called()
            self.assertIn('không bổ sung ảnh', reply)
            listing = backend.get('/listings?community_id=demo', headers={'X-API-Key': 'admin'}).json()[0]
            self.assertEqual((listing['status'], listing['images']), ('pending', []))


class LegacyMigration(unittest.TestCase):
    """A DB created before images/parts existed keeps queued and sent rows usable."""

    def test_old_queued_and_sent_rows_survive_upgrade_and_photos_v2(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'market.db'
            with closing(sqlite3.connect(path)) as db:
                db.executescript('''
                    CREATE TABLE listings (id TEXT PRIMARY KEY, community_id TEXT NOT NULL, seller_id TEXT NOT NULL,
                        title TEXT NOT NULL, price_vnd INTEGER NOT NULL, condition TEXT NOT NULL,
                        status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                    CREATE TABLE listing_deliveries (id TEXT PRIMARY KEY, listing_id TEXT NOT NULL, community_id TEXT NOT NULL,
                        target_group_id TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                        claim_token TEXT, claimed_at TEXT, lease_expires_at TEXT, last_error TEXT, sent_message_id TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(listing_id, target_group_id));
                    CREATE TABLE delivery_reconciliations (delivery_id TEXT NOT NULL, decision TEXT NOT NULL,
                        reason TEXT NOT NULL, reviewer TEXT NOT NULL DEFAULT 'admin-key',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                    INSERT INTO listings VALUES ('NM-OLDSENT0001','demo','seller','Tủ cũ',300000,'Còn tốt','approved',CURRENT_TIMESTAMP);
                    INSERT INTO listings VALUES ('NM-OLDQUEUE001','demo','seller','Ghế cũ',200000,'Còn tốt','approved',CURRENT_TIMESTAMP);
                    INSERT INTO listing_deliveries(id,listing_id,community_id,target_group_id,status,attempts,sent_message_id)
                        VALUES ('a'||hex(randomblob(15)),'NM-OLDSENT0001','demo','legit','sent',1,'mock-old');
                    INSERT INTO listing_deliveries(id,listing_id,community_id,target_group_id,status)
                        VALUES ('b'||hex(randomblob(15)),'NM-OLDQUEUE001','demo','legit','queued');
                ''')
                db.execute("UPDATE listing_deliveries SET id=lower(substr(id||'0000000000000000000000000000000000',1,32))")
                db.commit()
            app = create_app(path, 'bridge', 'admin', target_group_id='legit', publication_mode='photos_v2')
            with TestClient(app) as client:
                bridge = {'X-API-Key': 'bridge', 'X-Publisher-Version': '2'}
                job = client.post('/deliveries/claim', headers=bridge).json()
                self.assertEqual((job['part_type'], job['has_image']), ('post_text', False))
                self.assertIn('NM-OLDQUEUE001', job['message'])
                client.post(f"/deliveries/{job['delivery_id']}/sent", headers=bridge, json={
                    'claim_token': job['claim_token'], 'part_id': job['part_id'],
                    'sent_message_id': 'mock-new', 'transport_mode': 'mock'}).raise_for_status()
                sold = client.post('/events', headers=bridge, json={'event_id': 'e1', 'community_id': 'demo',
                                   'sender_id': 'seller', 'text': 'daban NM-OLDSENT0001'})
                self.assertEqual(sold.status_code, 200)
                notice = client.post('/deliveries/claim', headers=bridge).json()
                self.assertEqual(notice['part_type'], 'sold_notice')
                rows = {r['listing_id']: r for r in client.get('/deliveries?community_id=demo', headers={'X-API-Key': 'admin'}).json()}
                old = rows['NM-OLDSENT0001']['parts']
                self.assertEqual([(p['kind'], p['status'], p['sent_message_id']) for p in old][0], ('post_text', 'sent', 'mock-old'))
                self.assertEqual(rows['NM-OLDQUEUE001']['status'], 'sent')


if __name__ == '__main__':
    unittest.main()
