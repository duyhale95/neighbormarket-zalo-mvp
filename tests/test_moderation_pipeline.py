import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.moderation import assess_listing


class ModerationPipelineTests(unittest.TestCase):
    def test_advisory_report_never_auto_approves_or_claims_calibration(self):
        report=assess_listing('Ghế công thái học','dùng 6 tháng',800000)
        self.assertEqual(report.risk_level,'low')
        self.assertIsNone(report.risk_score)
        self.assertTrue(report.requires_review)
        self.assertTrue(report.policy_version)
        suspicious=assess_listing('Máy giặt','chuyển khoản trước, đặt cọc trước',1)
        self.assertEqual(suspicious.risk_level,'attention')
        self.assertIn('suspicious',suspicious.categories)
        self.assertNotIn('lừa đảo',suspicious.reason)
        # Single prohibited words retain accents to avoid "phao bơi" false positives.
        self.assertNotIn('prohibited',assess_listing('Phao bơi','mới',50000).categories)
        self.assertIn('prohibited',assess_listing('Súng','mới',500000).categories)

    def test_human_gate_and_backward_compatible_listing_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(Path(directory)/'db','bridge','admin',target_group_id='group')) as client:
                bridge={'X-API-Key':'bridge'}; admin={'X-API-Key':'admin'}
                for index,title in enumerate(['Ghế','Súng','Ghế 0912345678']):
                    event={'event_id':str(index),'community_id':'demo','sender_id':'seller',
                           'text':f'ban {title} | 800000 | dùng 6 tháng','source_channel':'deplao'}
                    draft=client.post('/events',headers=bridge,json=event).json()
                    self.assertEqual(draft['status'],'draft')
                    client.post('/events',headers=bridge,json={**event,'event_id':str(index)+'c',
                                'text':'xacnhan '+draft['listing_id']})
                    row=client.get('/listings?community_id=demo',headers=admin).json()[0]
                    self.assertEqual(row['status'],'pending')
                    self.assertIsInstance(row['moderation_flags'],str)
                    self.assertEqual(row['source_channel'],'deplao')
                    self.assertTrue(row['moderation']['requires_review'])
                    response=client.post('/listings/'+row['id']+'/review',headers=admin,
                        json={'community_id':'demo','action':'approve','reason':'QA review'})
                    self.assertEqual(response.status_code,200 if index==0 else 422)
                jobs=client.get('/deliveries?community_id=demo',headers=admin).json()
                self.assertEqual(len(jobs),1)
