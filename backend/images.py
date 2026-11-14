"""Private product media in the authoritative DB; no authenticity claims.

Normalization, moderation states and snapshot ideas adapted from main d28faeef.
Target ownership, revision checks, route auth and immutable review are canonical.
"""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import time
import warnings
from uuid import uuid4

import httpx
from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import Response
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from backend.image_fetch import MAX_BYTES, fetch_zalo


def prepare_image(raw: bytes) -> tuple[bytes, str, str]:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('Ảnh tối đa 4 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as original:
                if original.format not in ('JPEG','PNG','WEBP') or original.width * original.height > 16_000_000 or getattr(original,'n_frames',1) != 1:
                    raise ValueError('Chỉ nhận ảnh tĩnh JPEG/PNG/WebP, tối đa 16 triệu pixel.')
                original.load()
                image = ImageOps.exif_transpose(original).convert('RGB')
                image.thumbnail((1600,1600))
                # Copy pixels into a fresh image: no EXIF/XMP/ICC or other metadata.
                clean = Image.new('RGB', image.size); clean.paste(image)
                stream = io.BytesIO(); clean.save(stream,format='JPEG',quality=88)
    except (OSError,SyntaxError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise ValueError('Không đọc được ảnh hoặc ảnh vượt giới hạn.') from None
    data = stream.getvalue()
    return data, 'image/jpeg', hashlib.sha256(data).hexdigest()


class SafetyResult(BaseModel):
    model_config = ConfigDict(strict=True, extra='ignore')
    status: str
    categories: list[str] = Field(default_factory=list, max_length=50)
    model: str = Field(default='unavailable', max_length=100)


class OpenAIModerator:
    def __init__(self, key: str | None, *, model: str = 'omni-moderation-latest', transport=None):
        self.key, self.model, self.transport = key, model, transport

    def check(self, data: bytes, mime: str, text: str) -> dict:
        if not self.key:
            return {'status':'unavailable','categories':[], 'model':'unavailable'}
        try:
            with httpx.Client(transport=self.transport, timeout=httpx.Timeout(5,connect=2), trust_env=False) as client:
                response = client.post('https://api.openai.com/v1/moderations', headers={'Authorization':'Bearer '+self.key},
                    json={'model':self.model,'input':[{'type':'text','text':text[:2000]},
                    {'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+base64.b64encode(data).decode()}}]})
                response.raise_for_status()
                body=response.json(); result=body['results'][0]
                if type(result['flagged']) is not bool or not isinstance(result['categories'],dict) or any(type(v) is not bool for v in result['categories'].values()):
                    raise ValueError()
                return {'status':'flagged' if result['flagged'] else 'clear',
                    'categories':[k for k,v in result['categories'].items() if v and re.fullmatch(r'[a-z_/-]{1,80}',k)],'model':self.model}
        except (httpx.HTTPError,KeyError,IndexError,ValueError,TypeError):
            return {'status':'error','categories':[], 'model':self.model}


def text_digest(row) -> str:
    return hashlib.sha256(json.dumps([row['title'],row['price_vnd'],row['condition']],ensure_ascii=False).encode()).hexdigest()


class Upload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    community_id: str = Field(min_length=1,max_length=100)
    image_base64: str = Field(min_length=1,max_length=5_600_000)


class ImageEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    community_id: str = Field(min_length=1,max_length=100)
    sender_id: str = Field(min_length=1,max_length=100)
    event_id: str = Field(min_length=1,max_length=200)
    url: str = Field(min_length=1,max_length=12000)


class ImageStore:
    def __init__(self, database, moderator=None):
        self.database = database
        enabled=os.getenv('IMAGE_MODERATION_ENABLED','false').lower()=='true'
        self.moderator = moderator or OpenAIModerator(os.getenv('IMAGE_MODERATION_API_KEY') if enabled else None,
            model=os.getenv('IMAGE_MODERATION_MODEL','omni-moderation-latest'))
        with database() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS listing_images (
                    id TEXT PRIMARY KEY,listing_id TEXT NOT NULL,community_id TEXT NOT NULL,
                    digest TEXT NOT NULL,data BLOB NOT NULL,mime TEXT NOT NULL,status TEXT NOT NULL,
                    categories TEXT NOT NULL,model TEXT NOT NULL,text_digest TEXT NOT NULL,
                    version TEXT NOT NULL,updated_at REAL NOT NULL,UNIQUE(listing_id,digest));
                CREATE TABLE IF NOT EXISTS image_events (
                    community_id TEXT NOT NULL,sender_id TEXT NOT NULL,event_id TEXT NOT NULL,response TEXT NOT NULL,
                    PRIMARY KEY(community_id,sender_id,event_id));
                CREATE TABLE IF NOT EXISTS image_reviews (
                    listing_id TEXT NOT NULL,snapshot TEXT NOT NULL,reason TEXT NOT NULL,
                    reviewer TEXT NOT NULL DEFAULT 'admin-key',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            ''')

    def metadata(self, db, listing_id: str) -> list[dict]:
        listing=db.execute('SELECT * FROM listings WHERE id=?',(listing_id,)).fetchone()
        if not listing: return []
        return [{'id':r['id'],'status':('stale' if r['status']!='pending' and r['text_digest']!=text_digest(listing) else r['status']),
            'categories':json.loads(r['categories']),'model':r['model'],'revision':r['version']}
            for r in db.execute('SELECT * FROM listing_images WHERE listing_id=? ORDER BY rowid',(listing_id,))]

    def review_token(self, db, listing_id: str) -> str:
        listing=db.execute('SELECT * FROM listings WHERE id=?',(listing_id,)).fetchone()
        rows=[tuple(r) for r in db.execute('SELECT id,digest,status,categories,text_digest,version FROM listing_images WHERE listing_id=? ORDER BY rowid',(listing_id,))]
        return hashlib.sha256(json.dumps([text_digest(listing),rows],ensure_ascii=False).encode()).hexdigest()

    def guard(self, db, listing_id: str, token: str | None, manual: bool, reason: str) -> str:
        images=self.metadata(db,listing_id)
        current=self.review_token(db,listing_id)
        if images and not hmac.compare_digest(current.encode(),(token or '').encode()):
            raise HTTPException(409,'Ảnh/nội dung thay đổi; tải lại và xem đúng phiên bản trước khi duyệt.')
        if any(i['status']=='pending' for i in images):
            raise HTTPException(409,'Ảnh đang kiểm tra; chưa thể duyệt.')
        if any(i['status']!='clear' for i in images):
            if not manual or not reason.strip():
                raise HTTPException(409,'Cần BQL trực tiếp xem ảnh và ghi nhận kiểm tra thủ công.')
        if images and manual:
            db.execute('INSERT INTO image_reviews(listing_id,snapshot,reason) VALUES (?,?,?)',(listing_id,current,reason))
        return current

    def _result(self, data: bytes, mime: str, text: str) -> dict:
        try:
            result=SafetyResult.model_validate(self.moderator.check(data,mime,text)).model_dump()
            if result['status'] not in ('clear','flagged','error','unavailable'): raise ValueError()
            return result
        except Exception:
            # SDK errors can contain keys and input: never persist their exception text.
            return {'status':'error','categories':[],'model':'unavailable'}

    def upload(self, listing_id: str, community: str, raw: bytes, *, seller: str | None = None, context_revision: int | None = None) -> dict:
        try: data,mime,digest=prepare_image(raw)
        except ValueError as error: raise HTTPException(422,str(error)) from None
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM listings WHERE id=? AND community_id=?',(listing_id,community)).fetchone()
            if not row or (seller is not None and seller!=row['seller_id']): raise HTTPException(404,'Listing not found')
            if row['status'] not in ('draft','pending'): raise HTTPException(409,'Chỉ thêm ảnh trước khi duyệt.')
            if context_revision is not None:
                current=db.execute('SELECT * FROM conversations WHERE community_id=? AND sender_id=?',(community,seller)).fetchone()
                if not current or current['listing_id']!=listing_id or current['revision']!=context_revision:
                    raise HTTPException(409,'Bản nháp đã thay đổi trong lúc tải ảnh; chưa gắn ảnh vào tin mới.')
            prior=db.execute('SELECT id,status FROM listing_images WHERE listing_id=? AND digest=?',(listing_id,digest)).fetchone()
            if prior: return {'image_id':prior['id'],'status':prior['status']}
            if db.execute('SELECT count(*) FROM listing_images WHERE listing_id=?',(listing_id,)).fetchone()[0]>=5:
                raise HTTPException(409,'Mỗi tin tối đa 5 ảnh.')
            image_id,version=uuid4().hex,uuid4().hex
            text='\n'.join(str(row[k]) for k in ('title','price_vnd','condition'))
            db.execute('INSERT INTO listing_images VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (image_id,listing_id,community,digest,data,mime,'pending','[]','pending',text_digest(row),version,time.time()))
        result=self._result(data,mime,text)  # no model or network call inside DB transaction
        with self.database() as db:
            db.execute('UPDATE listing_images SET status=?,categories=?,model=? WHERE id=? AND version=?',
                (result['status'],json.dumps(result['categories']),result['model'],image_id,version))
        return {'image_id':image_id,**result}

    def recheck(self, image_id: str, community: str) -> dict:
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT i.*,l.title,l.price_vnd,l.condition,l.status AS listing_status FROM listing_images i JOIN listings l ON l.id=i.listing_id WHERE i.id=? AND i.community_id=?',(image_id,community)).fetchone()
            if not row: raise HTTPException(404,'Image not found')
            if row['listing_status'] not in ('draft','pending'): raise HTTPException(409,'Ảnh đã duyệt không được thay đổi.')
            if row['status']=='pending' and time.time()-row['updated_at']<60: raise HTTPException(409,'Ảnh đang kiểm tra.')
            version=uuid4().hex
            db.execute("UPDATE listing_images SET status='pending',version=?,updated_at=?,text_digest=? WHERE id=?",(version,time.time(),text_digest(row),image_id))
        result=self._result(row['data'],row['mime'],'\n'.join(str(row[k]) for k in ('title','price_vnd','condition')))
        with self.database() as db:
            db.execute('UPDATE listing_images SET status=?,categories=?,model=? WHERE id=? AND version=?',
                (result['status'],json.dumps(result['categories']),result['model'],image_id,version))
        return {'image_id':image_id,**result}

    def receive_zalo(self, url: str, community: str, sender: str, event_id: str) -> dict:
        identity=(community,sender,event_id)
        with self.database() as db:
            cached=db.execute('SELECT response FROM image_events WHERE community_id=? AND sender_id=? AND event_id=?',identity).fetchone()
            if cached: return json.loads(cached['response'])
            context=db.execute("SELECT c.listing_id,c.revision FROM conversations c JOIN listings l ON l.id=c.listing_id WHERE c.community_id=? AND c.sender_id=? AND l.seller_id=? AND l.status='draft'",(community,sender,sender)).fetchone()
            if not context: raise HTTPException(409,'Nhắn đủ thông tin để tạo bản nháp trước, rồi gửi ảnh trước khi xác nhận.')
        try: raw=fetch_zalo(url)
        except ValueError as error: raise HTTPException(422,str(error)) from None
        result=self.upload(context['listing_id'],community,raw,seller=sender,context_revision=context['revision'])
        result={**result,'listing_id':context['listing_id'],'reply':f"Đã lưu ảnh cho {context['listing_id']}. BQL vẫn cần xem ảnh và duyệt tin. Nhắn xác nhận khi đã đủ thông tin."}
        with self.database() as db:
            db.execute('INSERT OR IGNORE INTO image_events VALUES (?,?,?,?)',(*identity,json.dumps(result,ensure_ascii=False)))
            return json.loads(db.execute('SELECT response FROM image_events WHERE community_id=? AND sender_id=? AND event_id=?',identity).fetchone()['response'])

    def install(self, app, authenticate, bridge_key: str, admin_key: str, *, enabled: bool, community: str):
        @app.get('/images/{image_id}',dependencies=[Depends(authenticate(admin_key))])
        def preview(image_id: str,community_id: str=Query(min_length=1,max_length=100)):
            with self.database() as db:
                row=db.execute('SELECT data,mime FROM listing_images WHERE id=? AND community_id=?',(image_id,community_id)).fetchone()
                if not row: raise HTTPException(404,'Image not found')
                return Response(row['data'],media_type=row['mime'],headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"})

        @app.post('/images/{image_id}/recheck',dependencies=[Depends(authenticate(admin_key))])
        def recheck(image_id: str,community_id: str=Query(min_length=1,max_length=100)):
            return self.recheck(image_id,community_id)

        @app.post('/listings/{listing_id}/images',dependencies=[Depends(authenticate(admin_key))])
        async def upload(listing_id: str,request: Request):
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>6*1024*1024: raise HTTPException(413,'Upload tối đa 6 MiB.')
            try:
                body=Upload.model_validate_json(raw)
                data=base64.b64decode(body.image_base64,validate=True)
            except (ValueError,ValidationError): raise HTTPException(422,'Dữ liệu upload không hợp lệ.') from None
            return await run_in_threadpool(self.upload,listing_id,body.community_id,data)

        @app.post('/image-events',dependencies=[Depends(authenticate(bridge_key))])
        def image_event(body: ImageEvent):
            if not enabled: raise HTTPException(503,'Image transport disabled until metadata and strict Deplao build verified.')
            if body.community_id!=community: raise HTTPException(403,'Community outside trusted scope')
            return self.receive_zalo(body.url,community,body.sender_id,body.event_id)
