import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.ai import extract_listing
from backend.moderation import moderation_flags


class AIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name) / 'db.sqlite', 'bridge', 'admin'))
        self.bridge = {'X-API-Key': 'bridge'}
        self.admin = {'X-API-Key': 'admin'}
        self.seq = 0

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def event(self, text, event_id=None):
        self.seq += 1
        return self.client.post('/events', headers=self.bridge, json={
            'event_id': event_id or str(self.seq), 'community_id': 'demo',
            'sender_id': 'seller', 'text': text,
        })

    def extraction(self, **kwargs):
        return {'intent': 'sell', 'title': 'Bàn học gỗ', 'price_vnd': 400000,
                'condition': 'Dùng 1 năm', 'missing_fields': [], 'risk_flags': [], **kwargs}

    @patch('backend.app.extract_listing')
    def test_natural_language_creates_owned_draft_and_deduplicates(self, extract):
        extract.return_value = self.extraction()
        with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}):
            first = self.event('Mình muốn bán bàn học giá 400 nghìn dùng 1 năm', 'same').json()
            second = self.event('Mình muốn bán bàn học giá 400 nghìn dùng 1 năm', 'same').json()
        self.assertEqual(first, second)
        self.assertEqual(first['status'], 'draft')
        rows = self.client.get('/listings?community_id=demo', headers=self.admin).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['seller_id'], 'seller')
        self.assertEqual(rows[0]['price_vnd'], 400000)
        self.assertEqual(self.event('xacnhan ' + first['listing_id']).json()['status'], 'pending')

    @patch('backend.app.extract_listing')
    def test_missing_information_asks_user_without_creating_draft(self, extract):
        extract.return_value = self.extraction(price_vnd=None, condition=None, missing_fields=['price_vnd', 'condition'])
        with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}):
            result = self.event('Mình muốn bán bàn học').json()
        self.assertIn('giá', result['reply'].lower())
        self.assertIn('tình trạng', result['reply'].lower())
        self.assertEqual(self.client.get('/listings?community_id=demo', headers=self.admin).json(), [])

    @patch('backend.app.extract_listing', side_effect=httpx.TimeoutException('timeout'))
    def test_timeout_falls_back_to_commands(self, extract):
        with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}):
            result = self.event('Mình muốn bán bàn học').json()
        self.assertIn('giá', result['reply'])

    @patch('backend.app.extract_listing')
    def test_deterministic_commands_never_call_ai(self, extract):
        with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}):
            result = self.event('ban Ghế | 500 | cũ').json()
        self.assertEqual(result['status'], 'draft')
        extract.assert_not_called()

    def test_moderation_flags_visible_to_admin_after_confirmation(self):
        draft = self.event('ban Ghế liên hệ 0912345678 | 500 | cũ').json()
        self.event('xacnhan ' + draft['listing_id'])
        rows = self.client.get('/listings?community_id=demo', headers=self.admin).json()
        self.assertIn('sensitive_information', json.loads(rows[0]['moderation_flags']))

    @patch('backend.app.OpenAIModerator.check_text', create=True)
    def test_confirmed_listing_shows_omni_labels_without_auto_approval(self, check_text):
        check_text.return_value = {'status': 'flagged', 'categories': ['harassment'],
                                   'model': 'omni-moderation-latest'}
        with patch.dict('os.environ', {'TEXT_MODERATION_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}):
            draft = self.event('ban Ghế | 500000 | cũ').json()
            result = self.event('xacnhan ' + draft['listing_id'], 'confirmation')
            self.assertEqual(result.json()['status'], 'pending')
            self.event('xacnhan ' + draft['listing_id'], 'confirmation')
        check_text.assert_called_once_with('Ghế\ncũ')
        listing = self.client.get('/listings?community_id=demo', headers=self.admin).json()[0]
        self.assertEqual(listing['moderation']['omni']['categories'], ['harassment'])
        self.assertEqual(listing['moderation']['omni']['status'], 'flagged')

    @patch('backend.app.OpenAIModerator.check_text')
    def test_legacy_draft_has_complete_report_after_omni_check(self, check_text):
        check_text.return_value = {'status': 'clear', 'categories': [],
                                   'model': 'omni-moderation-latest'}
        draft_id = self.event('ban Ghế | 500000 | cũ').json()['listing_id']
        connection = sqlite3.connect(Path(self.tmp.name) / 'db.sqlite')
        try:
            with connection:
                connection.execute("UPDATE listings SET moderation_report='{}' WHERE id=?", (draft_id,))
        finally:
            connection.close()
        with patch.dict('os.environ', {'TEXT_MODERATION_ENABLED': 'true'}):
            self.event('xacnhan ' + draft_id).raise_for_status()
        report = self.client.get('/listings?community_id=demo', headers=self.admin).json()[0]['moderation']
        self.assertEqual(report['risk_level'], 'low')
        self.assertIs(report['requires_review'], True)
        self.assertEqual(report['omni']['status'], 'clear')


class OpenAIContractTests(unittest.TestCase):
    def test_structured_response_is_validated(self):
        extracted = {'intent': 'sell', 'title': 'Bàn học', 'price_vnd': 400000,
                     'condition': 'Đã dùng 1 năm', 'missing_fields': [], 'risk_flags': []}
        def handler(request):
            payload = json.loads(request.content)
            self.assertFalse(payload['store'])
            self.assertTrue(payload['text']['format']['strict'])
            self.assertEqual(payload['model'], 'test-model')
            return httpx.Response(200, request=request, json={'status': 'completed', 'output': [
                {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(extracted)}]}]})
        original_post = httpx.post
        def post(url, **kwargs):
            return httpx.Client(transport=httpx.MockTransport(handler)).post(url, **kwargs)
        with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake', 'OPENAI_MODEL': 'test-model'}), patch('backend.ai.httpx.post', side_effect=post):
            self.assertEqual(extract_listing('Bán bàn học giá 400 nghìn đã dùng 1 năm'), extracted)

    def test_prices_and_condition_must_be_grounded_in_message(self):
        for message, expected_price in [('Bàn cũ 400 nghìn', 400000), ('Bàn cũ 1 triệu', 1000000),
                                        ('Bàn cũ giá 400000, còn tốt', 400000), ('Bàn cũ giá 400.000', 400000)]:
            extraction = {'intent': 'sell', 'title': 'Bàn', 'price_vnd': expected_price,
                          'condition': 'cũ', 'missing_fields': [], 'risk_flags': []}
            response = httpx.Response(200, request=httpx.Request('POST', 'https://example.test'),
                json={'status': 'completed', 'output': [{'type': 'message', 'content': [
                    {'type': 'output_text', 'text': json.dumps(extraction)}]}]})
            with self.subTest(message=message), patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}), patch('backend.ai.httpx.post', return_value=response):
                self.assertEqual(extract_listing(message), extraction)

    def test_ungrounded_price_and_condition_are_removed(self):
        extraction = {'intent': 'sell', 'title': 'Bàn', 'price_vnd': 400000,
                      'condition': 'mới tinh', 'missing_fields': [], 'risk_flags': []}
        response = httpx.Response(200, request=httpx.Request('POST', 'https://example.test'),
            json={'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps(extraction)}]}]})
        with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}), patch('backend.ai.httpx.post', return_value=response):
            result = extract_listing('Bàn đã dùng từ năm 400000, chưa nói giá')
        self.assertIsNone(result['price_vnd'])
        self.assertIsNone(result['condition'])
        self.assertEqual(set(result['missing_fields']), {'price_vnd', 'condition'})

    def test_refusal_and_invalid_schema_return_fallback(self):
        for content in ([{'type': 'refusal', 'refusal': 'No'}],
                        [{'type': 'output_text', 'text': '{"intent":"approve"}'}]):
            with self.subTest(content=content):
                response = httpx.Response(200, request=httpx.Request('POST', 'https://example.test'),
                    json={'status': 'completed', 'output': [{'type': 'message', 'content': content}]})
                with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}), patch('backend.ai.httpx.post', return_value=response):
                    self.assertIsNone(extract_listing('text'))

    def test_unexpected_response_shape_returns_fallback(self):
        response = httpx.Response(200, request=httpx.Request('POST', 'https://example.test'), json=[])
        with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}), patch('backend.ai.httpx.post', return_value=response):
            self.assertIsNone(extract_listing('text'))

    def test_disabled_or_missing_key_avoids_network(self):
        with patch.dict('os.environ', {'AI_ENABLED': 'false', 'OPENAI_API_KEY': ''}), patch('backend.ai.httpx.post') as post:
            self.assertIsNone(extract_listing('text'))
            post.assert_not_called()

    def test_address_and_apartment_details_are_flagged(self):
        for content in ('căn 1203, tòa A', 'Căn hộ 15B', 'phòng 202',
                        'Số 12 đường Nguyễn Huệ', 'chung cư A1'):
            with self.subTest(content=content):
                self.assertIn('sensitive_information', moderation_flags('Ghế', content))

    def test_moderation_flags_are_conservative_signals(self):
        self.assertIn('sensitive_information', moderation_flags('Ghế', 'Liên hệ a@example.com'))
        self.assertIn('spam', moderation_flags('Ghế', 'xem https://example.com'))
        self.assertIn('suspicious', moderation_flags('Bàn', 'chuyển khoản trước'))
        self.assertIn('profanity', moderation_flags('Ghế', 'fuck'))
        self.assertEqual(moderation_flags('Bàn học', 'Đã dùng 1 năm'), [])


if __name__ == '__main__':
    unittest.main()
