import unittest
from unittest.mock import Mock, patch
import httpx

from backend.image_fetch import _download, validate_zalo_url, MAX_BYTES
from backend.images import OpenAIModerator


class ImageFetchTests(unittest.TestCase):
    def test_unsafe_urls_dns_redirects_and_size_are_rejected(self):
        for url in ('http://photo-zalo.zadn.vn/a','https://127.0.0.1/a','https://photo-zalo.zadn.vn.evil.test/a',
                    'https://photo-zalo.zadn.vn:444/a','https://x@photo-zalo.zadn.vn/a',
                    'https://photo-zalo.zadn.vn/a#fragment','https://unverified.zcdn.me/a'):
            with self.assertRaises(ValueError): validate_zalo_url(url)
        url='https://photo-zalo.zadn.vn/a?private-signature=synthetic'
        with patch('backend.image_fetch.socket.getaddrinfo',return_value=[(0,0,0,'',('127.0.0.1',443))]),patch('backend.image_fetch.http.client.HTTPSConnection') as connection:
            with self.assertRaises(ValueError): _download(url)
            connection.assert_not_called()
        for status,size in ((302,None),(403,None),(200,str(MAX_BYTES+1))):
            response=Mock(status=status); response.getheader.return_value=size
            with patch('backend.image_fetch.socket.getaddrinfo',return_value=[(0,0,0,'',('8.8.8.8',443))]),patch('backend.image_fetch.http.client.HTTPSConnection') as connection:
                connection.return_value.getresponse.return_value=response
                with self.assertRaises(ValueError): _download(url)
                connection.return_value.close.assert_called_once()

    def test_global_ip_is_pinned_with_original_tls_hostname_and_bounded_bytes(self):
        url='https://photo-stal-7.zdn.vn/product.jpg'
        response=Mock(status=200); response.getheader.return_value='3'; response.read1.side_effect=[b'abc',b'']
        with patch('backend.image_fetch.socket.getaddrinfo',return_value=[(0,0,0,'',('8.8.8.8',443))]) as dns,patch('backend.image_fetch.http.client.HTTPSConnection') as connection,patch('backend.image_fetch.socket.create_connection') as socket:
            connection.return_value.getresponse.return_value=response
            self.assertEqual(_download(url),b'abc')
            self.assertEqual(connection.call_args.args[0],'photo-stal-7.zdn.vn')
            connection.return_value._create_connection(('rebound.test',443),timeout=2)
            self.assertEqual(socket.call_args.args[0],('8.8.8.8',443))
            self.assertEqual(dns.call_count,1)

    def test_optional_moderator_fails_closed_and_uses_only_mock_http(self):
        self.assertEqual(OpenAIModerator(None).check(b'img','image/jpeg','text')['status'],'unavailable')
        for body,expected in (({'results':[{'flagged':False,'categories':{'violence':False}}]},'clear'),
                              ({'results':[{'flagged':True,'categories':{'violence':True}}]},'flagged'),
                              ({'results':[{'flagged':'false','categories':{}}]},'error')):
            def respond(request):
                self.assertEqual(str(request.url),'https://api.openai.com/v1/moderations')
                return httpx.Response(200,json=body)
            result=OpenAIModerator('mock-key',transport=httpx.MockTransport(respond)).check(b'synthetic','image/jpeg','test')
            self.assertEqual(result['status'],expected)
        def timeout(request): raise httpx.ReadTimeout('no network')
        self.assertEqual(OpenAIModerator('mock',transport=httpx.MockTransport(timeout)).check(b'img','image/jpeg','test')['status'],'error')
