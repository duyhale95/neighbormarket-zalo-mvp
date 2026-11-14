"""Authenticated adapter for a trusted, independently verified chat connector.

The connector must map its transport's metadata to IntakeEvent; this module
makes no assumptions about Deplao's message schema or delivery guarantees.
"""
import hmac
import os
from typing import Literal, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, StrictBool, field_validator


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
                      community_id: str, *, client: Optional[httpx.Client] = None) -> FastAPI:
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

    @app.post('/intake', dependencies=[Depends(authenticate)])
    def intake(event: IntakeEvent):
        if event.is_self or event.thread_type != 'private':
            return {'ignored': True, 'thread_id': event.thread_id, 'reply': ''}
        payload = {'event_id': event.message_id, 'community_id': community_id,
                   'sender_id': event.sender_id, 'text': event.text,
                   'thread_type': event.thread_type, 'is_self': event.is_self}
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

    return app


def from_environment() -> FastAPI:
    return create_intake_app(os.environ['BACKEND_URL'], os.environ['BRIDGE_API_KEY'],
                             os.environ['INTAKE_API_KEY'], os.environ['COMMUNITY_ID'])
