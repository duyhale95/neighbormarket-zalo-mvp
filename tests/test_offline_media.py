import unittest
from tools.offline_media_demo import run_demo


class OfflineMediaTests(unittest.TestCase):
    def test_image_inclusive_offline_pipeline_and_sold_notice(self):
        result=run_demo()
        self.assertEqual(result['parent_status'],'sent')
        self.assertEqual(len(result['receipts']),4)
        self.assertEqual(len(set(result['receipts'])),4)
        self.assertTrue(result['sold_removed_from_search'])
