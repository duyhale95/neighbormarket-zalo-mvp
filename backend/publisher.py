"""One-shot outbox consumer. Never retry a send whose outcome is uncertain.

Deplao uses the generated graph for live sends; this same protocol exercises
the backend with a deterministic transport. No undocumented Deplao REST API.
"""
import re
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.channels import SendOutcome, ZaloTransport


class DeliveryJob(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True)
    delivery_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    claim_token: str = Field(pattern=r'^[A-Za-z0-9_-]{20,100}$')
    group_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    attempt: int = Field(ge=1)


class PublishResult(BaseModel):
    status: Literal['idle', 'sent', 'failed', 'unknown']
    delivery_id: str | None = None
    simulated: bool
    acknowledgement_recorded: bool = False


class Publisher:
    def __init__(self, client: httpx.Client, bridge_key: str, transport: ZaloTransport,
                 group_id: str, *, policy_validated: bool = False):
        if not bridge_key or not group_id:
            raise ValueError('Bridge key and allowlisted group required')
        if transport.mode != 'mock' and not policy_validated:
            raise ValueError('Validate human policy and channel before enabling live publication')
        self.client, self.headers = client, {'X-API-Key': bridge_key}
        self.transport, self.group_id = transport, group_id

    def process_once(self) -> PublishResult:
        simulated = self.transport.mode == 'mock'
        response = self.client.post('/deliveries/claim', headers=self.headers, timeout=8)
        if response.status_code == 204:
            return PublishResult(status='idle', simulated=simulated)
        if response.status_code != 200:
            raise RuntimeError('Delivery claim rejected; inspect backend configuration')
        try:
            job = DeliveryJob.model_validate(response.json())
        except (ValidationError, ValueError):
            # A malformed claim might already be committed. Leave it for lease expiry.
            return PublishResult(status='unknown', simulated=simulated)
        if job.group_id != self.group_id:
            outcome = SendOutcome(status='not_sent', error='send_rejected', simulated=simulated)
        else:
            try:
                outcome = SendOutcome.model_validate(self.transport.send_group(job.group_id, job.message))
            except Exception:
                # Arbitrary transport errors can contain credentials. Do not log them,
                # and do not assume the remote send failed just because a call threw.
                outcome = SendOutcome(status='unknown', error='connection_error', simulated=simulated)
        receipt_valid = bool(outcome.message_id and re.fullmatch(
            r'mock-[A-Za-z0-9-]{1,100}' if simulated else r'[0-9]{1,100}', outcome.message_id))
        if outcome.status == 'sent' and receipt_valid and outcome.simulated == simulated:
            try:
                ack = self.client.post(f'/deliveries/{job.delivery_id}/sent', headers=self.headers,
                    json={'claim_token': job.claim_token, 'sent_message_id': outcome.message_id,
                          'transport_mode': 'mock' if simulated else 'deplao'}, timeout=8)
                if ack.status_code == 200:
                    return PublishResult(status='sent', delivery_id=job.delivery_id, simulated=simulated,
                                         acknowledgement_recorded=True)
            except httpx.HTTPError:
                pass
            # ACK may have committed. Reading state is safe; sending again is not.
            try:
                saved = self.client.get(f'/deliveries/{job.delivery_id}', headers=self.headers, timeout=8)
                if saved.status_code == 200 and saved.json().get('status') == 'sent':
                    return PublishResult(status='sent', delivery_id=job.delivery_id, simulated=simulated,
                                         acknowledgement_recorded=True)
            except (httpx.HTTPError, ValueError):
                pass
        status = 'failed' if outcome.status == 'not_sent' else 'unknown'
        recorded = False
        try:
            failure = self.client.post(f'/deliveries/{job.delivery_id}/failure', headers=self.headers,
                json={'claim_token': job.claim_token, 'outcome': 'not_sent' if status == 'failed' else 'unknown',
                      'error': outcome.error or 'other'}, timeout=8)
            recorded = failure.status_code == 200
        except httpx.HTTPError:
            pass  # claimed -> unknown on expiry; never put back in queued.
        return PublishResult(status=status, delivery_id=job.delivery_id, simulated=simulated,
                             acknowledgement_recorded=recorded)
