import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.ai import ListingExtraction, ground_extraction
from tools.offline_demo import run_demo


class IntegratedDemoTests(unittest.TestCase):
    def test_five_scene_offline_demo_uses_one_database_and_simulated_evidence(self):
        with patch('httpx.post',side_effect=AssertionError('External HTTP forbidden')):
            result=run_demo()
        self.assertEqual(len(result['scenes']),5)
        self.assertEqual(result['group_messages'],1)
        self.assertEqual(result['transport_mode'],'mock')

    def test_old_database_migration_preserves_records_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE listings (id TEXT PRIMARY KEY,community_id TEXT NOT NULL,seller_id TEXT NOT NULL,'
                    'title TEXT NOT NULL,price_vnd INTEGER NOT NULL,condition TEXT NOT NULL,status TEXT NOT NULL,'
                    'created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
                db.execute("INSERT INTO listings(id,community_id,seller_id,title,price_vnd,condition,status) VALUES ('NM-LEGACY','demo','seller','Ghế',500000,'cũ','pending')")
            db.close()
            for _ in range(2):
                with TestClient(create_app(path,'bridge','admin')) as client:
                    row=client.get('/listings?community_id=demo',headers={'X-API-Key':'admin'}).json()[0]
                    self.assertEqual(row['id'],'NM-LEGACY')
                    self.assertEqual(row['source_channel'],'legacy')
                    self.assertIsNone(row['moderation'])
                    self.assertEqual(row['status'],'pending')

    def test_concurrent_duplicate_webhook_creates_one_listing(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(Path(directory)/'db','bridge','admin')) as client:
                event={'event_id':'same','community_id':'demo','sender_id':'seller','text':'ban Ghế | 800000 | dùng 6 tháng'}
                with ThreadPoolExecutor(max_workers=5) as pool:
                    responses=list(pool.map(lambda _:client.post('/events',headers={'X-API-Key':'bridge'},json=event),range(5)))
                self.assertTrue(all(response.status_code==200 for response in responses))
                self.assertEqual(len({response.json()['listing_id'] for response in responses}),1)
                self.assertEqual(len(client.get('/listings?community_id=demo',headers={'X-API-Key':'admin'}).json()),1)

    def test_invented_title_is_removed_from_model_output(self):
        extraction=ListingExtraction(intent='sell',title='Ghế nhập khẩu Nhật Bản',price_vnd=800000,
            condition='cũ',missing_fields=[],risk_flags=[])
        grounded=ground_extraction(extraction,'Mình bán chiếc ghế cũ, giá 800k')
        self.assertIsNone(grounded['title'])
        self.assertIn('title',grounded['missing_fields'])
