import unittest
from backend.vnd import parse_vnd
import test_media_images as fixtures


class MarketMessageTests(unittest.TestCase):
    setUp=fixtures.MediaImageTests.setUp
    tearDown=fixtures.MediaImageTests.tearDown
    event=fixtures.MediaImageTests.event

    def test_huy_nhap_alias_and_private_listing_details_have_scope_and_no_publish_claim(self):
        item=self.item
        details=self.event(item).json()['reply']
        self.assertIn('800.000',details)
        self.assertIn('Bản nháp',details)
        self.assertNotIn('đã đăng',details.lower())
        self.assertEqual(self.event(item,sender='buyer').status_code,404)
        self.assertEqual(self.event(item,community='other').status_code,404)
        self.assertEqual(self.event('hủy nháp').json()['status'],'cancelled')

    def test_vietnamese_prices_already_supported_without_new_engine(self):
        for text,value in [('500k',500000),('1tr2',1200000),('1,5 triệu',1500000)]:
            self.assertEqual(parse_vnd(text),value)
