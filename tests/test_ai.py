import json
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
        self.assertIn('ban Tên món', result['reply'])

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
            self.assertEqual(extract_listing('Bán bàn học'), extracted)

    def test_refusal_and_invalid_schema_return_fallback(self):
        for content in ([{'type': 'refusal', 'refusal': 'No'}],
                        [{'type': 'output_text', 'text': '{"intent":"approve"}'}]):
            with self.subTest(content=content):
                response = httpx.Response(200, request=httpx.Request('POST', 'https://example.test'),
                    json={'status': 'completed', 'output': [{'type': 'message', 'content': content}]})
                with patch.dict('os.environ', {'AI_ENABLED': 'true', 'OPENAI_API_KEY': 'fake'}), patch('backend.ai.httpx.post', return_value=response):
                    self.assertIsNone(extract_listing('text'))

    def test_disabled_or_missing_key_avoids_network(self):
        with patch.dict('os.environ', {'AI_ENABLED': 'false', 'OPENAI_API_KEY': ''}), patch('backend.ai.httpx.post') as post:
            self.assertIsNone(extract_listing('text'))
            post.assert_not_called()

    def test_moderation_flags_are_conservative_signals(self):
        self.assertIn('sensitive_information', moderation_flags('Ghế', 'Liên hệ a@example.com'))
        self.assertIn('spam', moderation_flags('Ghế', 'xem https://example.com'))
        self.assertIn('suspicious', moderation_flags('Bàn', 'chuyển khoản trước'))
        self.assertIn('profanity', moderation_flags('Ghế', 'fuck'))
        self.assertEqual(moderation_flags('Bàn học', 'Đã dùng 1 năm'), [])


if __name__ == '__main__':
    unittest.main()
