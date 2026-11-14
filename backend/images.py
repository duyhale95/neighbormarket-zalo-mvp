"""Private image intake + safety moderation. Does not establish authenticity/ownership."""
import base64
import hashlib
import hmac
import http.client
import io
import ipaddress
import json
import logging
import re
import socket
import ssl
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from urllib.parse import urlsplit
from uuid import uuid4
import httpx
from PIL import Image, ImageOps
from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='image-safety')
MAX_BYTES = 4 * 1024 * 1024


def prepare_image(raw):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('Ảnh tối đa 4 MiB.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        try:
            image = Image.open(io.BytesIO(raw))
            if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 16_000_000:
                raise ValueError('Chỉ nhận PNG/JPEG/WebP, tối đa 16 triệu pixel.')
            image.load()
            image = ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((1600, 1600))
            out = io.BytesIO(); image.save(out, format='JPEG', quality=88)
        except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ValueError('Không đọc được ảnh hoặc ảnh vượt giới hạn.') from None
    data = out.getvalue()
    return data, 'image/jpeg', hashlib.sha256(data).hexdigest()


def validate_zalo_url(url):
    try:
        p = urlsplit(url)
        host = p.hostname or ''
        # Photo hosts observed in real Deplao/Zalo incoming messages.
        allowed = host == 'photo-zalo.zadn.vn' or host.endswith('.zcdn.me') or bool(re.fullmatch(r'photo-stal-[0-9]{1,3}\.zdn\.vn',host))
        if p.scheme != 'https' or not allowed or p.username or p.password or p.port not in (None, 443) or len(url) > 12000:
            raise ValueError()
        if not host.isascii() or '..' in host:
            raise ValueError()
        return p
    except ValueError:
        raise ValueError('Chưa nhận diện được địa chỉ ảnh Zalo này. Bạn gửi lại ảnh trực tiếp hoặc tải ảnh lên dashboard nhé.') from None


class ImageHTTPError(ValueError):
    def __init__(self, status):
        self.status = status
        super().__init__(f'Máy chủ ảnh Zalo chưa cung cấp ảnh (HTTP {status}). Bạn đợi vài giây rồi gửi lại ảnh nhé.')


def _fetch_zalo_once(url):
    p = validate_zalo_url(url)
    addresses = {entry[4][0] for entry in socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses or not all(ipaddress.ip_address(a).is_global and not ipaddress.ip_address(a).is_multicast for a in addresses):
        raise ValueError('Địa chỉ ảnh không hợp lệ.')
    # Pin validated IP; TLS SNI/certificate validation still uses original host.
    connection = http.client.HTTPSConnection(p.hostname, 443, timeout=2, context=ssl.create_default_context())
    pinned = sorted(addresses)[0]
    connection._create_connection = lambda address, timeout=None, source_address=None: socket.create_connection((pinned, 443), timeout, source_address)
    try:
        connection.request('GET', p.path + ('?' + p.query if p.query else ''), headers={'User-Agent':'NeighborMarket-local-image'})
        response = connection.getresponse()
        if response.status != 200:  # No redirects to unvalidated destinations.
            raise ImageHTTPError(response.status)
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Ảnh tối đa 4 MiB.')
        return raw
    finally:
        connection.close()


def _fetch_zalo(url):
    validate_zalo_url(url)
    for attempt in range(3):
        try:
            return _fetch_zalo_once(url)
        except ImageHTTPError as error:
            logging.getLogger(__name__).warning('Zalo image CDN HTTP %s, attempt %s/3, host=%s',error.status,attempt+1,urlsplit(url).hostname)
            if error.status not in (403,404,408,429,500,502,503,504) or attempt==2:
                raise
            time.sleep((.4,1.2)[attempt])


def fetch_zalo(url):
    validate_zalo_url(url)
    future = _POOL.submit(_fetch_zalo, url)
    try:
        return future.result(timeout=8)
    except (FutureTimeout, OSError, http.client.HTTPException):
        future.cancel()
        raise ValueError('Tải ảnh chưa thành công. Bạn thử gửi lại ảnh nhé.') from None


class OpenAIModerator:
    def __init__(self, key, transport=None):
        self._key, self._transport = key, transport

    def check(self, data, mime, text):
        if not self._key:
            return {'status':'unavailable','categories':[]}
        task = _POOL.submit(self._check, data, mime, text)
        try:
            return task.result(timeout=10)
        except FutureTimeout:
            task.cancel()
            return {'status':'error','categories':[]}

    def _check(self, data, mime, text):
        try:
            with httpx.Client(transport=self._transport, timeout=httpx.Timeout(8, connect=2)) as client:
                response = client.post('https://api.openai.com/v1/moderations',
                    headers={'Authorization':'Bearer '+self._key}, json={'model':'omni-moderation-latest','input':[
                        {'type':'text','text':text[:4000]},
                        {'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+base64.b64encode(data).decode()}}]})
                response.raise_for_status(); result=response.json()['results'][0]
                if type(result['flagged']) is not bool or not isinstance(result['categories'],dict):
                    raise ValueError()
                if any(type(v) is not bool for v in result['categories'].values()):
                    raise ValueError()
                return {'status':'flagged' if result['flagged'] else 'clear',
                        'categories':[k for k,v in result['categories'].items() if v]}
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
            return {'status':'error','categories':[]}


class ImageStore:
    def __init__(self, database, moderator):
        self.database, self.moderator = database, moderator or OpenAIModerator(None)
        with database() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS listing_images (
                    id TEXT PRIMARY KEY, listing_id TEXT NOT NULL, community_id TEXT NOT NULL,
                    digest TEXT NOT NULL, data BLOB NOT NULL, mime TEXT NOT NULL,
                    status TEXT NOT NULL, categories TEXT NOT NULL, updated_at REAL NOT NULL, text_digest TEXT NOT NULL DEFAULT '',
                    UNIQUE(listing_id,digest)
                );
                CREATE TABLE IF NOT EXISTS image_overrides (
                    listing_id TEXT NOT NULL, reason TEXT NOT NULL, reviewed_at REAL NOT NULL, snapshot TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS image_events (
                    community_id TEXT NOT NULL,sender_id TEXT NOT NULL,event_id TEXT NOT NULL,response TEXT NOT NULL,
                    PRIMARY KEY(community_id,sender_id,event_id)
                );
            ''')
            if 'text_digest' not in [r[1] for r in db.execute('PRAGMA table_info(listing_images)')]:
                db.execute("ALTER TABLE listing_images ADD COLUMN text_digest TEXT NOT NULL DEFAULT ''")
            if 'snapshot' not in [r[1] for r in db.execute('PRAGMA table_info(image_overrides)')]:
                db.execute("ALTER TABLE image_overrides ADD COLUMN snapshot TEXT NOT NULL DEFAULT ''")

    def review_token(self, db, listing_id):
        listing=db.execute('SELECT title,price_vnd,condition FROM listings WHERE id=?',(listing_id,)).fetchone()
        rows=[tuple(r) for r in db.execute('SELECT id,status,categories,updated_at,text_digest FROM listing_images WHERE listing_id=? ORDER BY id',(listing_id,))]
        return hashlib.sha256(json.dumps([list(listing) if listing else None,rows],ensure_ascii=False).encode()).hexdigest()

    def metadata(self, db, listing_id):
        listing=db.execute('SELECT title,condition FROM listings WHERE id=?',(listing_id,)).fetchone()
        expected=hashlib.sha256((listing['title']+'\n'+listing['condition']).encode()).hexdigest() if listing else None
        return [{'id':r['id'],'status':'stale' if r['status']=='clear' and expected and r['text_digest']!=expected else r['status'],
                 'categories':json.loads(r['categories'])} for r in
                db.execute('SELECT id,status,categories,text_digest FROM listing_images WHERE listing_id=? ORDER BY rowid', (listing_id,))]

    def guard(self, db, listing_id, reviewed, reason, token):
        rows=self.metadata(db,listing_id)
        snapshot=self.review_token(db,listing_id)
        if rows and not hmac.compare_digest(snapshot.encode(),(token or '').encode()):
            raise HTTPException(409,'Ảnh hoặc nội dung đã thay đổi. Hãy tải lại danh sách và kiểm tra phiên bản mới trước khi duyệt.')
        if any(r['status']=='pending' for r in rows):
            raise HTTPException(409,'Ảnh đang được kiểm tra. Vui lòng đợi hoặc kiểm tra lại ảnh bị treo.')
        if any(r['status']!='clear' for r in rows):
            if not reviewed:
                raise HTTPException(409,'Ảnh bị gắn cờ hoặc chưa kiểm duyệt được. BQL cần xem ảnh và xác nhận đã kiểm tra thủ công.')
            db.execute('INSERT INTO image_overrides(listing_id,reason,reviewed_at,snapshot) VALUES (?,?,?,?)',(listing_id,reason,time.time(),snapshot))

    def upload(self, listing_id, community, raw, seller=None):
        try:data,mime,digest=prepare_image(raw)
        except ValueError as error:raise HTTPException(422,str(error)) from None
        with self.database(timeout=1) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM listings WHERE id=? AND community_id=?',(listing_id,community)).fetchone()
            context=db.execute('SELECT * FROM conversations WHERE listing_id=? AND community_id=?',(listing_id,community)).fetchone()
            owner=row['seller_id'] if row else context['sender_id'] if context else None
            if owner is None or (seller is not None and seller!=owner):raise HTTPException(404,'Listing not found')
            if row and row['status'] not in ('draft','pending'):raise HTTPException(409,'Chỉ thêm ảnh trước khi tin được duyệt.')
            prior=db.execute('SELECT id,status,categories FROM listing_images WHERE listing_id=? AND digest=?',(listing_id,digest)).fetchone()
            if prior:return {'image_id':prior['id'],'status':prior['status'],'categories':json.loads(prior['categories'])}
            if db.execute('SELECT count(*) FROM listing_images WHERE listing_id=?',(listing_id,)).fetchone()[0]>=5:
                raise HTTPException(409,'Mỗi tin tối đa 5 ảnh.')
            id=uuid4().hex
            text=(row['title']+'\n'+row['condition']) if row else context['data']
            db.execute('INSERT INTO listing_images(id,listing_id,community_id,digest,data,mime,status,categories,updated_at,text_digest) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (id,listing_id,community,digest,data,mime,'pending','[]',time.time(),hashlib.sha256(text.encode()).hexdigest()))
        try:result=self.moderator.check(data,mime,text)
        except Exception:result={'status':'error','categories':[]}
        if result.get('status') not in ('clear','flagged','error','unavailable'):
            result={'status':'error','categories':[]}
        with self.database(timeout=1) as db:
            db.execute('UPDATE listing_images SET status=?,categories=?,updated_at=? WHERE id=?',
                       (result['status'],json.dumps(result.get('categories',[])),time.time(),id))
        return {'image_id':id,**result}

    def recheck(self, image_id, community):
        with self.database(timeout=1) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT i.*,l.title,l.condition,l.status AS listing_status FROM listing_images i JOIN listings l ON l.id=i.listing_id WHERE i.id=? AND i.community_id=?',
                           (image_id,community)).fetchone()
            if not row:raise HTTPException(404,'Image not found')
            if row['listing_status'] not in ('draft','pending'):raise HTTPException(409,'Chỉ kiểm tra lại trước khi duyệt.')
            if row['status']=='pending' and time.time()-row['updated_at']<60:raise HTTPException(409,'Ảnh đang được kiểm tra.')
            text=row['title']+'\n'+row['condition']
            db.execute("UPDATE listing_images SET status='pending',updated_at=?,text_digest=? WHERE id=?",
                       (time.time(),hashlib.sha256(text.encode()).hexdigest(),image_id))
        try:result=self.moderator.check(row['data'],row['mime'],text)
        except Exception:result={'status':'error','categories':[]}
        if result.get('status') not in ('clear','flagged','error','unavailable'):result={'status':'error','categories':[]}
        with self.database(timeout=1) as db:
            db.execute('UPDATE listing_images SET status=?,categories=?,updated_at=? WHERE id=?',
                       (result['status'],json.dumps(result.get('categories',[])),time.time(),image_id))
        return {'image_id':image_id,**result}

    def receive_zalo(self, url, community, sender, event_id):
        identity=(community,sender,event_id)
        with self.database(timeout=1) as db:
            cached=db.execute('SELECT response FROM image_events WHERE community_id=? AND sender_id=? AND event_id=?',identity).fetchone()
            if cached:return json.loads(cached['response'])
            current=db.execute('SELECT listing_id FROM current_drafts WHERE community_id=? AND sender_id=?',(community,sender)).fetchone()
            if not current:raise HTTPException(409,'Bạn nhắn thông tin món cần bán trước, rồi gửi ảnh trước khi xác nhận nhé.')
            listing_id=current['listing_id']
        try:raw=fetch_zalo(url)
        except ValueError as error:raise HTTPException(422,str(error)) from None
        result=self.upload(listing_id,community,raw,seller=sender)
        reply='Đã nhận ảnh và kiểm tra an toàn sơ bộ; BQL vẫn sẽ duyệt tin.' if result['status']=='clear' else 'Đã nhận ảnh. Ảnh cần BQL kiểm tra thủ công trước khi được duyệt.'
        result={**result,'listing_id':listing_id,'reply':reply+' Bạn tiếp tục bổ sung thông tin còn thiếu hoặc nhắn xác nhận khi bản nháp đầy đủ.'}
        with self.database(timeout=1) as db:
            db.execute('INSERT OR IGNORE INTO image_events VALUES (?,?,?,?)',(*identity,json.dumps(result,ensure_ascii=False)))
        return result

    def install(self, app, authenticate, bridge_key, admin_key):
        @app.post('/images/{image_id}/recheck',dependencies=[Depends(authenticate(admin_key))])
        def recheck(image_id:str,community_id:str=Query(min_length=1,max_length=100)):
            return self.recheck(image_id,community_id)

        @app.get('/images/{image_id}',dependencies=[Depends(authenticate(admin_key))])
        def image(image_id:str,community_id:str=Query(min_length=1,max_length=100)):
            with self.database(timeout=1) as db:
                row=db.execute('SELECT data,mime FROM listing_images WHERE id=? AND community_id=?',(image_id,community_id)).fetchone()
                if not row:raise HTTPException(404,'Image not found')
                return Response(row['data'],media_type=row['mime'],headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

        @app.post('/listings/{listing_id}/images',dependencies=[Depends(authenticate(admin_key))])
        async def upload(listing_id:str,request:Request):
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>6*1024*1024:raise HTTPException(413,'Upload tối đa 6 MiB.')
            try:
                body=json.loads(raw);community=body['community_id']
                if not isinstance(community,str) or not 1<=len(community)<=100:raise ValueError()
                data=base64.b64decode(body['image_base64'],validate=True)
            except (ValueError,KeyError,TypeError):raise HTTPException(422,'Dữ liệu upload ảnh không hợp lệ.') from None
            return await run_in_threadpool(self.upload,listing_id,community,data)

        @app.post('/bridge/zalo-image',dependencies=[Depends(authenticate(bridge_key))])
        async def zalo_image(request:Request):
            sender,event_id=request.headers.get('x-sender-id',''),request.headers.get('x-event-id','')
            if not 1<=len(sender)<=100 or not 1<=len(event_id)<=200:raise HTTPException(422,'Missing image metadata')
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>16000:raise HTTPException(413,'Image URL too long')
            try:
                url=raw.decode('utf-8').removeprefix('NM-IMAGE:\n').strip()
                import os
                return await run_in_threadpool(self.receive_zalo,url,os.getenv('DEMO_COMMUNITY_ID','demo'),sender,event_id)
            except (HTTPException,ValueError,UnicodeDecodeError) as error:
                return {'reply':str(error.detail) if isinstance(error,HTTPException) else 'Chưa nhận được ảnh hợp lệ. Bạn thử lại nhé.','business_status':getattr(error,'status_code',422)}
