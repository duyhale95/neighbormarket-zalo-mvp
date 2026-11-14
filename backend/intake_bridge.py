"""Authenticated adapter for a trusted, independently verified chat connector.

The connector must map its transport's metadata to IntakeEvent; this module
makes no assumptions about Deplao's message schema or delivery guarantees.
"""
import hmac
import os
from typing import Literal, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, StrictBool, field_validator
from starlette.concurrency import run_in_threadpool

from backend.channels import normalize_deplao


class IntakeEvent(BaseModel):
    message_id: str = Field(min_length=1, max_length=200)
    sender_id: str = Field(min_length=1, max_length=100)
    thread_id: str = Field(min_length=1, max_length=200)
    thread_type: Literal['private', 'group']
    is_self: StrictBool
    text: str = Field(min_length=1, max_length=4000)

    @field_validator('message_id', 'sender_id', 'thread_id')
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('identifier must not be blank')
        return value

    class Config:
        extra = 'forbid'


def create_intake_app(backend_url: str, backend_key: str, intake_key: str,
                      community_id: str, *, client: Optional[httpx.Client] = None,
                      account_id: str | None = None,
                      allowed_sender_ids: set[str] | None = None, images_enabled: bool = False) -> FastAPI:
    """Create a bridge; only a trusted connector may call its /intake endpoint."""
    if not all(value and value.strip() for value in (backend_url, backend_key, intake_key, community_id)):
        raise ValueError('Backend URL, distinct keys and community ID must be configured')
    if hmac.compare_digest(backend_key.encode(), intake_key.encode()):
        raise ValueError('Use different backend and intake keys')
    endpoint = backend_url.rstrip('/') + '/events'
    app = FastAPI(title='NeighborMarket trusted intake adapter')

    def authenticate(x_intake_key: str = Header(default='')) -> None:
        if not hmac.compare_digest(x_intake_key.encode(), intake_key.encode()):
            raise HTTPException(status_code=401, detail='Invalid intake key')

    @app.get('/health')
    def health():
        return {'status': 'ok', 'connector': 'unverified', 'mode': 'trusted-intake',
                'text_only': True, 'account_configured': bool(account_id)}

    def forward(event: IntakeEvent, source_channel: str = 'legacy'):
        if event.is_self or event.thread_type != 'private':
            return {'ignored': True, 'thread_id': event.thread_id, 'reply': ''}
        payload = {'event_id': event.message_id, 'community_id': community_id,
                   'sender_id': event.sender_id, 'text': event.text,
                   'thread_type': event.thread_type, 'is_self': event.is_self,
                   'source_channel': source_channel}
        try:
            if client is None:
                response = httpx.post(endpoint, json=payload, headers={'X-API-Key': backend_key}, timeout=8.0)
            else:
                response = client.post(endpoint, json=payload, headers={'X-API-Key': backend_key}, timeout=8.0)
            if response.status_code == 200:
                body = response.json()
                reply = body.get('reply') if isinstance(body, dict) else None
                if isinstance(reply, str):
                    return {'ignored': bool(body.get('ignored', False)), 'thread_id': event.thread_id, 'reply': reply}
                reply = 'Hệ thống tạm thời không xử lý được. Vui lòng liên hệ BQL.'
            elif response.status_code == 404:
                reply = 'Không tìm thấy tin phù hợp với tài khoản của bạn.'
            elif response.status_code == 409:
                reply = 'Trạng thái tin không cho phép thao tác này.'
            elif response.status_code == 422:
                reply = 'Nội dung chưa hợp lệ. Hãy kiểm tra lệnh và thông tin sản phẩm.'
            else:
                reply = 'Hệ thống tạm thời không xử lý được. Vui lòng liên hệ BQL.'
        except (httpx.RequestError, ValueError):
            # A timeout can occur after the backend has committed the operation.
            reply = 'Hệ thống tạm thời chưa xác định được kết quả. Vui lòng liên hệ BQL kiểm tra.'
        return {'ignored': False, 'thread_id': event.thread_id, 'reply': reply}

    @app.post('/intake', dependencies=[Depends(authenticate)])
    async def intake(request: Request):
        # Bound the stream even if Content-Length is absent or dishonest.
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 20000:
                raise HTTPException(413, 'Message too large')
        content_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
        try:
            if content_type == 'application/json':
                event = IntakeEvent.model_validate_json(raw)
                return await run_in_threadpool(forward, event)
            if content_type != 'text/plain':
                raise HTTPException(415, 'Use application/json or text/plain')
            if not account_id:
                raise HTTPException(503, 'Configure the trusted account before Deplao intake')
            text = raw.decode('utf-8')
            if not text.startswith('NM-TEXT:\n'):
                raise ValueError('Missing fixed raw-text prefix')
            headers = request.headers
            account = headers.get('x-zalo-account', '')
            sender = headers.get('x-zalo-sender', '')
            if account != account_id or (allowed_sender_ids is not None and sender not in allowed_sender_ids):
                raise HTTPException(403, 'Account or sender outside configured scope')
            if headers.get('x-zalo-self') not in ('true', 'false') or headers.get('x-zalo-thread-type') not in ('0', '1'):
                raise ValueError('Missing trusted metadata')
            message = normalize_deplao({'zaloId': account, 'fromId': sender,
                'threadId': headers.get('x-zalo-thread', ''), 'msgId': headers.get('x-zalo-message', ''),
                'threadType': int(headers['x-zalo-thread-type']), 'isSelf': headers['x-zalo-self'] == 'true',
                'content': text[len('NM-TEXT:\n'):]}, account_id)
            if message is None:
                return {'ignored': True, 'thread_id': headers.get('x-zalo-thread', ''), 'reply': ''}
            event = IntakeEvent(message_id=message.event_id, sender_id=message.sender_id,
                thread_id=message.thread_id, thread_type='private', is_self=False, text=message.text)
            return await run_in_threadpool(forward, event, 'deplao')
        except (ValueError, UnicodeError):
            raise HTTPException(422, 'Malformed text or transport metadata') from None

    @app.post('/intake/image', dependencies=[Depends(authenticate)])
    async def image_intake(request: Request):
        if not images_enabled: raise HTTPException(503,'Image metadata and strict runtime not verified; image intake disabled')
        if not account_id: raise HTTPException(503,'Configure trusted account')
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>16000: raise HTTPException(413,'Image reference too large')
        if request.headers.get('content-type','').split(';')[0]!='text/plain': raise HTTPException(415,'Use text/plain')
        headers=request.headers
        if headers.get('x-zalo-account')!=account_id or (allowed_sender_ids is not None and headers.get('x-zalo-sender') not in allowed_sender_ids):
            raise HTTPException(403,'Account or sender outside trusted scope')
        try:
            body=raw.decode('utf-8')
            if not body.startswith('NM-IMAGE:\n') or headers.get('x-zalo-self') not in ('true','false') or headers.get('x-zalo-thread-type') not in ('0','1'):
                raise ValueError()
            message=normalize_deplao({'zaloId':account_id,'fromId':headers.get('x-zalo-sender',''),
                'threadId':headers.get('x-zalo-thread',''),'msgId':headers.get('x-zalo-message',''),
                'threadType':int(headers['x-zalo-thread-type']),'isSelf':headers['x-zalo-self']=='true','content':'image'},account_id)
            if message is None: return {'ignored':True,'thread_id':headers.get('x-zalo-thread',''),'reply':''}
            from backend.image_fetch import validate_zalo_url
            url=body[len('NM-IMAGE:\n'):].strip(); validate_zalo_url(url)
        except (ValueError,UnicodeError): raise HTTPException(422,'Malformed image reference or metadata') from None
        def forward_image():
            try:
                payload={'event_id':'image-'+message.event_id,'sender_id':message.sender_id,'community_id':community_id,'url':url}
                call=client.post if client is not None else httpx.post
                response=call(backend_url.rstrip('/')+'/image-events',json=payload,headers={'X-API-Key':backend_key},timeout=25)
                data=response.json() if response.status_code==200 else {}
                reply=data.get('reply') if isinstance(data,dict) else None
                # Fixed copy per status; never echo backend detail text to the resident.
                if not isinstance(reply,str): reply={
                    409:'Chưa lưu ảnh: chỉ nhận ảnh khi bạn đang có bản nháp chưa xác nhận (tối đa 5 ảnh). '
                        'Tin đã gửi BQL hoặc đã duyệt không bổ sung ảnh được; hãy tạo tin mới nếu cần đăng kèm ảnh.',
                    422:'Chưa lưu ảnh: chỉ nhận ảnh tĩnh JPEG, PNG hoặc WebP, tối đa 4 MiB.',
                }.get(response.status_code,'Chưa lưu được ảnh. Kiểm tra bản nháp, kết nối và cấu hình với BQL.')
            except (httpx.HTTPError,ValueError):
                reply='Chưa xác định được kết quả lưu ảnh. Nhờ BQL kiểm tra trước khi gửi lại.'
            return {'ignored':False,'thread_id':message.thread_id,'reply':reply}
        return await run_in_threadpool(forward_image)

    return app


def from_environment() -> FastAPI:
    from backend.runtime_config import images_enabled
    return create_intake_app(os.environ['BACKEND_URL'], os.environ['BRIDGE_API_KEY'],
                             os.environ['INTAKE_API_KEY'], os.environ['COMMUNITY_ID'],
                             account_id=os.getenv('ZALO_ACCOUNT_ID'),
                             allowed_sender_ids=set(filter(None, os.getenv('ZALO_TEST_SENDER_IDS', '').split(','))) or None,
                             images_enabled=images_enabled())
