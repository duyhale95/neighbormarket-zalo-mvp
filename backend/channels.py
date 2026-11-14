"""Transport contracts, separate from marketplace state and credentials.

Strict parse/ignore distinction inspired by VHR-07 (MIT; see THIRD_PARTY_NOTICES).
Deplao fields verified against WorkflowEngineService.flattenTriggerData.
"""
import hashlib
import json
import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class Attachment(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    mime_type: str
    reference: str
    size_bytes: int | None = Field(default=None, ge=0)


class InboundMessage(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    event_id: str = Field(min_length=1, max_length=200)
    account_id: str = Field(min_length=1, max_length=100)
    sender_id: str = Field(min_length=1, max_length=100)
    thread_id: str = Field(min_length=1, max_length=200)
    channel: Literal['deplao', 'mock']
    message_type: Literal['text', 'image']
    text: str = Field(max_length=4000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=5)
    timestamp: int | None = Field(default=None, ge=0)
    is_self: StrictBool


class SendOutcome(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['sent', 'not_sent', 'unknown']
    message_id: str | None = Field(default=None, max_length=200)
    error: Literal['timeout', 'connection_error', 'send_rejected', 'other'] | None = None
    simulated: bool = False


class ConnectionHealth(BaseModel):
    mode: Literal['mock', 'deplao']
    status: Literal['simulated', 'unverified', 'connected', 'disconnected']
    evidence: str


class ZaloTransport(Protocol):
    """No Bot Platform token is accepted by this personal-account interface."""
    mode: Literal['mock', 'deplao']

    def receive(self, metadata: dict[str, Any]) -> InboundMessage | None: ...
    def send_private(self, thread_id: str, text: str) -> SendOutcome: ...
    def send_group(self, group_id: str, text: str) -> SendOutcome: ...
    def health(self) -> ConnectionHealth: ...


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,100}', value):
        raise ValueError('Missing or malformed transport identifier')
    return value


def normalize_deplao(raw: dict[str, Any], account_id: str) -> InboundMessage | None:
    """Normalize verified flattened trigger metadata; never read identity from text."""
    account = _identifier(raw.get('zaloId'))
    if account != account_id:
        raise ValueError('Unexpected account')
    sender = _identifier(raw.get('fromId'))
    thread = _identifier(raw.get('threadId'))
    message = _identifier(raw.get('msgId'))
    thread_type = raw.get('threadType')
    if type(thread_type) is not int or thread_type not in (0, 1):
        raise ValueError('Missing or invalid thread type')
    if type(raw.get('isSelf')) is not bool:
        raise ValueError('Missing self-message indicator')
    if raw['isSelf'] or thread_type != 0:
        return None
    if not isinstance(raw.get('content'), str) or not raw['content'].strip():
        raise ValueError('Text-only message required')
    stable = json.dumps([account, sender, thread, message], separators=(',', ':'))
    return InboundMessage(event_id='deplao:' + hashlib.sha256(stable.encode()).hexdigest(),
                          account_id=account, sender_id=sender, thread_id=thread, channel='deplao',
                          message_type='text', text=raw['content'], timestamp=raw.get('timestamp'), is_self=False)


class MockZaloTransport:
    """Explicit simulator; records test sends in memory and never opens a socket."""
    mode = 'mock'

    def __init__(self, account_id: str, group_id: str):
        self.account_id, self.group_id = account_id, group_id
        self.sent: list[dict[str, str]] = []

    def receive(self, metadata: dict[str, Any]) -> InboundMessage | None:
        event = normalize_deplao(metadata, self.account_id)
        return event.model_copy(update={'channel': 'mock'}) if event else None

    def _send(self, kind: str, thread_id: str, text: str) -> SendOutcome:
        if not text.strip():
            return SendOutcome(status='not_sent', error='send_rejected', simulated=True)
        self.sent.append({'kind': kind, 'thread_id': thread_id, 'text': text})
        return SendOutcome(status='sent', message_id=f'mock-{len(self.sent)}', simulated=True)

    def send_private(self, thread_id: str, text: str) -> SendOutcome:
        return self._send('private', thread_id, text)

    def send_group(self, group_id: str, text: str) -> SendOutcome:
        if group_id != self.group_id:
            return SendOutcome(status='not_sent', error='send_rejected', simulated=True)
        return self._send('group', group_id, text)

    def health(self) -> ConnectionHealth:
        return ConnectionHealth(mode='mock', status='simulated', evidence='In-memory test transport; no Zalo session')
