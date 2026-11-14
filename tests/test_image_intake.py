import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.intake_bridge import create_intake_app
from backend.runtime_config import images_enabled
from tools.deplao_compat import STRICT_ENGINE_SHA256
from tools.build_deplao_workflows import build_image_intake
from test_media_images import photo, Moderator


class ImageIntakeTests(unittest.TestCase):
    def test_raw_image_metadata_dedup_self_group_and_account_scope(self):
        with tempfile.TemporaryDirectory() as temp,TestClient(create_app(Path(temp)/'db.sqlite','bridge','admin',image_moderator=Moderator(),zalo_images_enabled=True)) as backend:
            backend.post('/events',headers={'X-API-Key':'bridge'},json={'event_id':'draft','community_id':'demo','sender_id':'202','text':'ban Ghế | 500000 | còn tốt'}).raise_for_status()
            with TestClient(create_intake_app('http://backend','bridge','intake','demo',client=backend,account_id='303',allowed_sender_ids={'202'},images_enabled=True)) as adapter:
                headers={'X-Intake-Key':'intake','Content-Type':'text/plain','X-Zalo-Account':'303','X-Zalo-Sender':'202','X-Zalo-Thread':'202','X-Zalo-Message':'101','X-Zalo-Thread-Type':'0','X-Zalo-Self':'false'}
                raw='NM-IMAGE:\nhttps://photo-zalo.zadn.vn/synthetic.jpg'
                # A valid JPEG may carry large metadata. The normalized copy is small.
                oversized = photo() + b'\0' * (4 * 1024 * 1024)
                with patch('backend.images.fetch_zalo',return_value=oversized) as fetch:
                    result=adapter.post('/intake/image',headers=headers,content=raw)
                    self.assertEqual(result.status_code,200); self.assertIn('đã lưu ảnh',result.json()['reply'])
                    self.assertEqual(adapter.post('/intake/image',headers=headers,content=raw).json(),result.json()); self.assertEqual(fetch.call_count,1)
                    for field,value in [('X-Zalo-Self','true'),('X-Zalo-Thread-Type','1')]:
                        self.assertTrue(adapter.post('/intake/image',headers={**headers,field:value},content=raw).json()['ignored'])
                    self.assertEqual(adapter.post('/intake/image',headers={**headers,'X-Zalo-Account':'404'},content=raw).status_code,403)
                    self.assertEqual(adapter.post('/intake/image',headers=headers,content='NM-IMAGE:\nhttps://127.0.0.1/private').status_code,422)
                    self.assertEqual(fetch.call_count,1)
            with TestClient(create_intake_app('http://backend','bridge','intake','demo',client=backend)) as disabled:
                self.assertEqual(disabled.post('/intake/image',headers={'X-Intake-Key':'intake'}).status_code,503)

    def test_runtime_images_need_strict_manifest_and_metadata_not_env_alone(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True):
            path=Path(temp)/'channel.json';os.environ.update(ZALO_IMAGES_ENABLED='true',ZALO_CHANNEL_CONFIG=str(path))
            with self.assertRaises(OSError): images_enabled()
            values={'strict_account_binding_verified':True,'policy_validated':True,'image_metadata_verified':True,
                'images_enabled':True,'deplao_engine_sha256':'wrong'}
            path.write_text(json.dumps(values))
            with self.assertRaises(ValueError): images_enabled()
            values['deplao_engine_sha256']=STRICT_ENGINE_SHA256;path.write_text(json.dumps(values))
            self.assertTrue(images_enabled())
            os.environ['ZALO_ACCOUNT_ID']='unexpected'
            with self.assertRaises(ValueError): images_enabled()

    def test_generator_photo_mapping_requires_explicit_metadata_attestation(self):
        with self.assertRaises(ValueError): build_image_intake('test-intake-key-123456','303','202',binding_verified=True)
        graph=build_image_intake('test-intake-key-123456','303','202',binding_verified=True,image_metadata_verified=True)
        nodes={n['label']:n for n in graph['nodes']}
        self.assertEqual(nodes['ReceivePrivate']['config']['messageTypes'],['image'])
        self.assertEqual(nodes['Intake']['config']['body'],'NM-IMAGE:\n{{ $trigger.images.0 }}')
