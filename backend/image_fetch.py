"""Time-limited Zalo CDN download. Adapted from reviewed main images.py.

Only trusted photo metadata may reach this module, never a URL parsed from PM text.
No redirects/proxy; validate ALL DNS answers, pin one IP, retain original TLS SNI.
"""
import http.client
import ipaddress
import re
import socket
import ssl
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import BinaryIO
from urllib.parse import urlsplit, SplitResult

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='nm-image-fetch')
_SLOTS = threading.BoundedSemaphore(2)


def validate_zalo_url(url: str) -> SplitResult:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ''
        allowed = host == 'photo-zalo.zadn.vn' or bool(re.fullmatch(r'photo-stal-[0-9]{1,3}\.zdn\.vn', host))
        # Generic *.zcdn.me is deliberately NOT accepted without observed metadata.
        if (not allowed or parsed.scheme != 'https' or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.fragment or len(url) > 12000
                or any(ord(c) < 33 or c == '\\' for c in url) or not host.isascii()):
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise ValueError('Địa chỉ ảnh không thuộc CDN Zalo được cho phép.') from None


def _download(url: str) -> BinaryIO:
    started = time.monotonic()
    parsed = validate_zalo_url(url)
    addresses = {r[4][0] for r in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(a).is_global or ipaddress.ip_address(a).is_multicast for a in addresses):
        raise ValueError('Địa chỉ máy chủ ảnh không an toàn.')
    connection = http.client.HTTPSConnection(parsed.hostname, 443, timeout=2, context=ssl.create_default_context())
    pinned = min(addresses, key=lambda address: (ipaddress.ip_address(address).version, address))
    connection._create_connection = lambda address, timeout=None, source_address=None: socket.create_connection((pinned, 443), timeout, source_address)
    try:
        if time.monotonic() - started > 6:
            raise ValueError('Tải ảnh quá thời gian.')
        connection.request('GET', parsed.path + ('?' + parsed.query if parsed.query else ''), headers={'User-Agent':'NeighborMarket-image-intake'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('CDN chưa trả ảnh hợp lệ; không chuyển hướng hoặc tự thử lại.')
        size = response.getheader('Content-Length')
        if size is not None and not size.isdigit():
            raise ValueError('CDN trả kích thước ảnh không hợp lệ.')
        raw = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b')
        try:
            while True:
                if time.monotonic() - started > 6:
                    raise ValueError('Tải ảnh quá thời gian.')
                chunk = response.read1(65536)
                if not chunk:
                    break
                raw.write(chunk)
            if size is not None and raw.tell() != int(size):
                raise ValueError('Ảnh tải chưa đầy đủ.')
            raw.seek(0)
            return raw
        except BaseException:
            raw.close()
            raise
    finally:
        connection.close()


def fetch_zalo(url: str) -> BinaryIO:
    validate_zalo_url(url)
    if not _SLOTS.acquire(blocking=False):
        raise ValueError('Đang tải ảnh khác; vui lòng thử sau.')
    future = _POOL.submit(_download, url)
    future.add_done_callback(lambda _: _SLOTS.release())
    try:
        return future.result(timeout=8)
    except FutureTimeout:
        if not future.cancel():
            def close_late_download(completed):
                if not completed.cancelled() and completed.exception() is None:
                    completed.result().close()
            future.add_done_callback(close_late_download)
        raise ValueError('Chưa tải được ảnh; kiểm tra kết nối rồi thử lại.') from None
    except (OSError, http.client.HTTPException):
        raise ValueError('Chưa tải được ảnh; kiểm tra kết nối rồi thử lại.') from None
