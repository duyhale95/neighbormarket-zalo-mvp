"""Local MVP. Only the trusted bridge may assert community/sender identity."""
import hmac
import hashlib
import json
import logging
import os
import re
import sqlite3
import secrets
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, ValidationError
import httpx

from backend.ai import ListingExtraction, extract_listing
from backend.moderation import BLOCKING_FLAGS, assess_listing, moderation_flags

audit_logger = logging.getLogger('neighbormarket.audit')
audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    audit_logger.addHandler(logging.StreamHandler())
audit_logger.propagate = False


def audit(action: str, **fields) -> None:
    """Emit only explicitly selected metadata; never include chat text or credentials."""
    audit_logger.info(json.dumps({'action': action, **fields}, ensure_ascii=False))


class Event(BaseModel):
    event_id: str = Field(min_length=1, max_length=200)
    community_id: str = Field(min_length=1, max_length=100)
    sender_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=4000)
    thread_type: Literal['private', 'group'] = 'private'
    is_self: bool = False
    source_channel: Literal['legacy', 'deplao', 'mock'] = 'legacy'


class Review(BaseModel):
    community_id: str = Field(min_length=1, max_length=100)
    action: Literal['approve', 'reject']
    reason: str = Field(min_length=1, max_length=1000)


class DeliveryAck(BaseModel):
    claim_token: str = Field(min_length=1, max_length=200)
    sent_message_id: str | None = Field(default=None, max_length=200)
    transport_mode: Literal['mock', 'deplao', 'unverified'] = 'unverified'


class DeliveryFailure(BaseModel):
    claim_token: str = Field(min_length=1, max_length=200)
    outcome: Literal['not_sent', 'unknown']
    error: str = Field(min_length=1, max_length=200)


class DeliveryReconciliation(BaseModel):
    decision: Literal['sent', 'not_sent']
    reason: str = Field(min_length=1, max_length=1000)
    sent_message_id: str | None = Field(default=None, max_length=200)


def normalize(value):
    value = unicodedata.normalize('NFD', value.casefold().replace('đ', 'd'))
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn')


def create_app(db_path, bridge_key, admin_key, *, target_group_id=None, target_community_id='demo'):
    if not bridge_key or not admin_key or bridge_key == admin_key:
        raise ValueError('Configure two different nonempty API keys')
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def database():
        db = sqlite3.connect(db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    with database() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY, community_id TEXT NOT NULL, seller_id TEXT NOT NULL,
                title TEXT NOT NULL, price_vnd INTEGER NOT NULL, condition TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS events (
                community_id TEXT NOT NULL, sender_id TEXT NOT NULL, event_id TEXT NOT NULL,
                response TEXT NOT NULL, PRIMARY KEY(community_id, sender_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS reviews (
                listing_id TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS listing_deliveries (
                id TEXT PRIMARY KEY, listing_id TEXT NOT NULL, community_id TEXT NOT NULL,
                target_group_id TEXT NOT NULL, status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, claim_token TEXT,
                claimed_at TEXT, lease_expires_at TEXT, last_error TEXT,
                sent_message_id TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(listing_id, target_group_id)
            );
            CREATE TABLE IF NOT EXISTS delivery_reconciliations (
                delivery_id TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL,
                reviewer TEXT NOT NULL DEFAULT 'admin-key',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS listings_scope ON listings(community_id, status);
        ''')
        columns = {row['name'] for row in db.execute('PRAGMA table_info(listings)')}
        if 'moderation_flags' not in columns:
            db.execute("ALTER TABLE listings ADD COLUMN moderation_flags TEXT NOT NULL DEFAULT '[]'")
        if 'moderation_report' not in columns:
            db.execute("ALTER TABLE listings ADD COLUMN moderation_report TEXT NOT NULL DEFAULT '{}'")
        if 'source_channel' not in columns:
            db.execute("ALTER TABLE listings ADD COLUMN source_channel TEXT NOT NULL DEFAULT 'legacy'")
        delivery_columns = {row['name'] for row in db.execute('PRAGMA table_info(listing_deliveries)')}
        if 'transport_mode' not in delivery_columns:
            db.execute("ALTER TABLE listing_deliveries ADD COLUMN transport_mode TEXT NOT NULL DEFAULT 'unverified'")

    app = FastAPI(title='NeighborMarket local MVP', version='0.1.0')

    def authenticate(expected):
        def check(x_api_key: str = Header(default='')):
            if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
                raise HTTPException(401, 'Invalid API key')
        return check

    def expire_claims(db):
        # An expired worker may have sent already: never requeue automatically.
        db.execute("""UPDATE listing_deliveries SET status='unknown',
                      last_error='claim_expired', updated_at=CURRENT_TIMESTAMP
                      WHERE status='claimed' AND lease_expires_at <= CURRENT_TIMESTAMP""")

    def public_delivery(row):
        return {key: row[key] for key in (
            'id', 'listing_id', 'community_id', 'target_group_id', 'status',
            'attempts', 'last_error', 'sent_message_id', 'created_at', 'updated_at', 'transport_mode')}

    def require_claim(db, delivery_id, claim_token):
        row = db.execute('SELECT * FROM listing_deliveries WHERE id=?', (delivery_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Delivery not found')
        if not row['claim_token'] or not hmac.compare_digest(row['claim_token'], claim_token):
            raise HTTPException(409, 'Invalid or stale claim')
        return row

    def public_text(value):
        return ' '.join(value.split())

    def listing_record(row):
        result = dict(row)
        raw = result.pop('moderation_report', '{}')
        result['moderation'] = json.loads(raw) or None
        return result

    @app.get('/health')
    def health():
        return {'status': 'ok', 'mode': 'local-mvp'}

    @app.get('/stats', dependencies=[Depends(authenticate(admin_key))])
    def stats(community_id: str = Query(min_length=1, max_length=100)):
        with database() as db:
            counts = {row['status']: row['n'] for row in db.execute(
                'SELECT status, COUNT(*) AS n FROM listings WHERE community_id=? GROUP BY status', (community_id,))}
            sent = db.execute("SELECT COUNT(*) AS n FROM listing_deliveries WHERE community_id=? AND status='sent'", (community_id,)).fetchone()['n']
            return {'total': sum(counts.values()), 'pending': counts.get('pending', 0),
                    'approved': counts.get('approved', 0), 'rejected': counts.get('rejected', 0),
                    'sold': counts.get('sold', 0), 'sent': sent}

    @app.get('/listings', dependencies=[Depends(authenticate(admin_key))])
    def listings(community_id: str = Query(min_length=1, max_length=100)):
        with database() as db:
            return [listing_record(row) for row in db.execute(
                'SELECT * FROM listings WHERE community_id=? ORDER BY rowid DESC LIMIT 100', (community_id,))]

    @app.post('/listings/{listing_id}/review', dependencies=[Depends(authenticate(admin_key))])
    def review(listing_id: str, request: Review):
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM listings WHERE id=? AND community_id=?',
                             (listing_id, request.community_id)).fetchone()
            if not row:
                raise HTTPException(404, 'Listing not found')
            if row['status'] != 'pending':
                raise HTTPException(409, 'Only pending listings may be reviewed')
            if request.action == 'approve' and BLOCKING_FLAGS.intersection(moderation_flags(row['title'], row['condition'])):
                raise HTTPException(422, 'Thông tin nhạy cảm hoặc mặt hàng bị cấm: từ chối và yêu cầu người bán viết lại.')
            status = 'approved' if request.action == 'approve' else 'rejected'
            db.execute('UPDATE listings SET status=? WHERE id=?', (status, listing_id))
            db.execute('INSERT INTO reviews(listing_id,action,reason) VALUES (?,?,?)',
                       (listing_id, request.action, request.reason))
            delivery_status = 'not_applicable' if status == 'rejected' else 'not_configured'
            if status == 'approved' and target_group_id and request.community_id == target_community_id:
                db.execute('INSERT INTO listing_deliveries(id,listing_id,community_id,target_group_id,status) VALUES (?,?,?,?,?)',
                           (uuid4().hex, listing_id, request.community_id, target_group_id, 'queued'))
                delivery_status = 'queued'
            db.commit()
            audit('review', listing_id=listing_id, actor='admin-key', status=status,
                  moderation_flags=json.loads(row['moderation_flags']), delivery_status=delivery_status)
            return {'listing_id': listing_id, 'status': status, 'delivery_status': delivery_status}

    @app.post('/deliveries/claim', dependencies=[Depends(authenticate(bridge_key))])
    def claim_delivery():
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            expire_claims(db)
            if not target_group_id:
                return Response(status_code=204)
            row = db.execute("""SELECT d.*, l.title, l.condition, l.price_vnd FROM listing_deliveries d
                JOIN listings l ON l.id=d.listing_id AND l.community_id=d.community_id
                WHERE d.status='queued' AND l.status='approved' AND d.target_group_id=?
                AND d.community_id=? ORDER BY d.rowid LIMIT 1""", (target_group_id, target_community_id)).fetchone()
            if not row:
                return Response(status_code=204)
            if BLOCKING_FLAGS.intersection(moderation_flags(row['title'], row['condition'])):
                db.execute("UPDATE listing_deliveries SET status='failed', last_error='sensitive_information', updated_at=CURRENT_TIMESTAMP WHERE id=?", (row['id'],))
                return Response(status_code=204)
            token = secrets.token_urlsafe(32)
            db.execute("""UPDATE listing_deliveries SET status='claimed', attempts=attempts+1,
                claim_token=?, claimed_at=CURRENT_TIMESTAMP,
                lease_expires_at=datetime('now','+5 minutes'), updated_at=CURRENT_TIMESTAMP WHERE id=?""", (token, row['id']))
            db.commit()
            audit('delivery', delivery_id=row['id'], listing_id=row['listing_id'], delivery_status='claimed')
            message = (f"[NEIGHBORMARKET — TIN ĐÃ DUYỆT]\n\nSản phẩm: {public_text(row['title'])}\n"
                       f"Giá: {row['price_vnd']:,}đ\nTình trạng: {public_text(row['condition'])}\n\n"
                       f"Mã tin: {row['listing_id']}\n\nNhắn riêng cho Meo Meo để tìm hiểu sản phẩm.")
            return {'delivery_id': row['id'], 'claim_token': token, 'group_id': row['target_group_id'],
                    'message': message, 'attempt': row['attempts'] + 1}

    @app.post('/deliveries/{delivery_id}/sent', dependencies=[Depends(authenticate(bridge_key))])
    def delivery_sent(delivery_id: str, request: DeliveryAck):
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            expire_claims(db)
            row = require_claim(db, delivery_id, request.claim_token)
            if row['status'] == 'sent' and row['sent_message_id'] == request.sent_message_id:
                return {'delivery_id': delivery_id, 'status': 'sent'}
            if row['status'] not in ('claimed', 'unknown'):
                raise HTTPException(409, 'Delivery cannot be acknowledged')
            db.execute("UPDATE listing_deliveries SET status='sent', sent_message_id=?, transport_mode=?, last_error=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (request.sent_message_id, request.transport_mode, delivery_id))
            db.commit()
            audit('delivery', delivery_id=delivery_id, listing_id=row['listing_id'], delivery_status='sent')
            return {'delivery_id': delivery_id, 'status': 'sent'}

    @app.post('/deliveries/{delivery_id}/failure', dependencies=[Depends(authenticate(bridge_key))])
    def delivery_failure(delivery_id: str, request: DeliveryFailure):
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            expire_claims(db)
            row = require_claim(db, delivery_id, request.claim_token)
            if row['status'] != 'claimed':
                raise HTTPException(409, 'Delivery is no longer claimed')
            status = 'unknown' if request.outcome == 'unknown' else 'failed'
            # Do not persist arbitrary SDK errors that might contain credentials.
            error = request.error if request.error in ('timeout', 'connection_error', 'send_rejected') else 'other'
            db.execute('UPDATE listing_deliveries SET status=?, last_error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (status, error, delivery_id))
            db.commit()
            audit('delivery', delivery_id=delivery_id, listing_id=row['listing_id'], delivery_status=status, error=error)
            return {'delivery_id': delivery_id, 'status': status}

    @app.get('/deliveries', dependencies=[Depends(authenticate(admin_key))])
    def deliveries(community_id: str = Query(min_length=1, max_length=100)):
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            expire_claims(db)
            return [public_delivery(row) for row in db.execute('SELECT * FROM listing_deliveries WHERE community_id=? ORDER BY rowid DESC LIMIT 100', (community_id,))]

    @app.get('/deliveries/{delivery_id}', dependencies=[Depends(authenticate(bridge_key))])
    def delivery_status(delivery_id: str):
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            expire_claims(db)
            row = db.execute('SELECT * FROM listing_deliveries WHERE id=?', (delivery_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Delivery not found')
            return public_delivery(row)

    @app.post('/deliveries/{delivery_id}/reconcile', dependencies=[Depends(authenticate(admin_key))])
    def reconcile_delivery(delivery_id: str, request: DeliveryReconciliation):
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            expire_claims(db)
            row = db.execute('SELECT * FROM listing_deliveries WHERE id=?', (delivery_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Delivery not found')
            if row['status'] != 'unknown':
                raise HTTPException(409, 'Only unknown deliveries may be reconciled')
            status = 'sent' if request.decision == 'sent' else 'failed'
            db.execute('INSERT INTO delivery_reconciliations(delivery_id,decision,reason) VALUES (?,?,?)', (delivery_id, request.decision, request.reason))
            db.execute('UPDATE listing_deliveries SET status=?, sent_message_id=?, claim_token=NULL, last_error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                       (status, request.sent_message_id if status == 'sent' else None, None if status == 'sent' else 'reconciled_not_sent', delivery_id))
            db.commit()
            audit('reconcile', actor='admin-key', delivery_id=delivery_id, listing_id=row['listing_id'], delivery_status=status)
            return {'delivery_id': delivery_id, 'status': status}

    @app.post('/events', dependencies=[Depends(authenticate(bridge_key))])
    def event(event: Event):
        if event.is_self or event.thread_type != 'private':
            return {'ignored': True, 'reply': ''}
        event_digest = hashlib.sha256(event.event_id.encode('utf-8')).hexdigest()
        identity = (event.community_id, event.sender_id, event.event_id)
        text = event.text.strip()
        command, _, body = text.partition(' ')
        command = normalize(command)
        body = body.strip()
        # Check the replay cache before network access, then recheck under the write lock.
        with database() as db:
            cached = db.execute('SELECT response FROM events WHERE community_id=? AND sender_id=? AND event_id=?', identity).fetchone()
        if cached:
            return json.loads(cached['response'])
        extracted = None
        if command not in ('ban', 'xacnhan', 'daban', 'tim'):
            ai_active = os.getenv('AI_ENABLED', '').lower() in ('1', 'true', 'yes') and bool(os.getenv('OPENAI_API_KEY', '').strip())
            started = time.monotonic()
            try:
                raw = extract_listing(text)
                if raw is not None:
                    extracted = ListingExtraction.model_validate(raw)
            except (httpx.HTTPError, ValueError, TypeError, ValidationError):
                extracted = None
            if ai_active:
                model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
                if not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', model):
                    model = 'invalid-model-name'
                audit('ai_extraction', event_id=event_digest, correlation_id=event_digest,
                      model=model, latency_ms=round((time.monotonic() - started) * 1000),
                      result='extracted' if extracted else 'fallback')
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            cached = db.execute('SELECT response FROM events WHERE community_id=? AND sender_id=? AND event_id=?', identity).fetchone()
            if cached:
                return json.loads(cached['response'])
            if command == 'ban' or (extracted and extracted.intent == 'sell'):
                if command == 'ban':
                    parts = [p.strip() for p in body.split('|')]
                    if len(parts) != 3 or not all(parts) or not parts[1].isascii() or not parts[1].isdigit():
                        raise HTTPException(422, 'Dùng: ban Tên món | Giá nguyên VND | Tình trạng')
                    title, price, condition = parts
                    price = int(price)
                    missing = []
                else:
                    title = (extracted.title or '').strip()
                    price = extracted.price_vnd
                    condition = (extracted.condition or '').strip()
                    missing = set(extracted.missing_fields)
                    if not title: missing.add('title')
                    if price is None: missing.add('price_vnd')
                    if not condition: missing.add('condition')
                if missing:
                    labels = {'title': 'tên sản phẩm', 'price_vnd': 'giá', 'condition': 'tình trạng'}
                    needed = ', '.join(labels[field] for field in ('title', 'price_vnd', 'condition') if field in missing)
                    result = {'reply': f'Bạn vui lòng cung cấp {needed}. Hãy gửi lại đầy đủ tên sản phẩm, giá VND và tình trạng.'}
                else:
                    if len(title) > 250 or len(condition) > 500 or not 0 <= price <= 1_000_000_000:
                        raise HTTPException(422, 'Tên, tình trạng hoặc giá vượt giới hạn')
                    report = assess_listing(title, condition, price, ai_flags=bool(extracted and extracted.risk_flags),
                        model_version=os.getenv('OPENAI_MODEL', 'gpt-4o-mini') if extracted else 'rules-only',
                        ai_status='advisory' if extracted else 'not_requested')
                    flags = report.categories
                    id = 'NM-' + uuid4().hex[:12].upper()
                    db.execute('INSERT INTO listings(id,community_id,seller_id,title,price_vnd,condition,status,moderation_flags) VALUES (?,?,?,?,?,?,?,?)',
                               (id, event.community_id, event.sender_id, title, price, condition, 'draft', json.dumps(flags)))
                    db.execute('UPDATE listings SET moderation_report=?, source_channel=? WHERE id=?',
                               (report.model_dump_json(), event.source_channel, id))
                    result = {'listing_id': id, 'status': 'draft',
                              'reply': f'Bản nháp {id}: {title}, {price:,}đ, {condition}. Nhắn xacnhan {id} để gửi BQL duyệt.'}
            elif command in ('xacnhan', 'daban'):
                row = db.execute('SELECT * FROM listings WHERE id=? AND community_id=? AND seller_id=?',
                                 (body, event.community_id, event.sender_id)).fetchone()
                if not row:
                    raise HTTPException(404, 'Listing not found')
                required, status = ('draft', 'pending') if command == 'xacnhan' else ('approved', 'sold')
                if row['status'] != required:
                    raise HTTPException(409, 'Listing is not in the required state')
                if status == 'sold':
                    expire_claims(db)
                    in_flight = db.execute("SELECT 1 FROM listing_deliveries WHERE listing_id=? AND status IN ('claimed','unknown')", (body,)).fetchone()
                    if in_flight:
                        raise HTTPException(409, 'Tin đang gửi hoặc cần BQL đối soát trước khi báo đã bán')
                    db.execute("UPDATE listing_deliveries SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE listing_id=? AND status='queued'", (body,))
                db.execute('UPDATE listings SET status=? WHERE id=?', (status, body))
                result = {'listing_id': body, 'status': status,
                          'reply': 'Đã gửi BQL duyệt.' if status == 'pending' else 'Đã đánh dấu bán xong.'}
            elif command == 'tim':
                terms = normalize(body).split()
                if not terms:
                    raise HTTPException(422, 'Nhập từ khóa sau tim')
                rows = db.execute("SELECT id,title,price_vnd,condition FROM listings WHERE community_id=? AND status='approved' ORDER BY rowid DESC", (event.community_id,))
                found = [dict(r) for r in rows if 'sensitive_information' not in moderation_flags(r['title'], r['condition'])
                         and all(term in normalize(r['title'] + ' ' + r['condition']) for term in terms)][:5]
                result = {'listings': found, 'reply': '\n'.join(f"{r['id']} — {r['title']} — {r['price_vnd']:,}đ" for r in found) or 'Chưa có tin phù hợp đã được duyệt.'}
            else:
                result = {'reply': 'Bạn có thể nhắn: ban Tên món | Giá VND | Tình trạng; tim từ khóa; xacnhan MÃ_TIN; daban MÃ_TIN. Đây là luồng nghiệp vụ thử nghiệm, chưa xử lý ảnh.'}
            db.execute('INSERT INTO events VALUES (?,?,?,?)', (*identity, json.dumps(result, ensure_ascii=False)))
            db.commit()
            audit('event', event_id=event_digest, correlation_id=event_digest,
                  listing_id=result.get('listing_id'), status=result.get('status'),
                  moderation_flags=flags if result.get('status') == 'draft' else [])
            return result

    return app


def from_environment():
    return create_app(os.getenv('DATABASE_PATH', 'private/market.db'),
                      os.environ['BRIDGE_API_KEY'], os.environ['ADMIN_API_KEY'],
                      target_group_id=os.getenv('ZALO_LEGIT_GROUP_ID'),
                      target_community_id=os.getenv('ZALO_COMMUNITY_ID', 'demo'))
