"""Local MVP. Only the trusted bridge may assert community/sender identity."""
import hmac
import json
import os
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field


class Event(BaseModel):
    event_id: str = Field(min_length=1, max_length=200)
    community_id: str = Field(min_length=1, max_length=100)
    sender_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=4000)
    thread_type: Literal['private', 'group'] = 'private'
    is_self: bool = False


class Review(BaseModel):
    community_id: str = Field(min_length=1, max_length=100)
    action: Literal['approve', 'reject']
    reason: str = Field(min_length=1, max_length=1000)


def normalize(value):
    value = unicodedata.normalize('NFD', value.casefold().replace('đ', 'd'))
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn')


def create_app(db_path, bridge_key, admin_key):
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
            CREATE INDEX IF NOT EXISTS listings_scope ON listings(community_id, status);
        ''')

    app = FastAPI(title='NeighborMarket local MVP', version='0.1.0')

    def authenticate(expected):
        def check(x_api_key: str = Header(default='')):
            if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
                raise HTTPException(401, 'Invalid API key')
        return check

    @app.get('/health')
    def health():
        return {'status': 'ok', 'mode': 'local-mvp'}

    @app.get('/listings', dependencies=[Depends(authenticate(admin_key))])
    def listings(community_id: str = Query(min_length=1, max_length=100)):
        with database() as db:
            return [dict(row) for row in db.execute(
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
            status = 'approved' if request.action == 'approve' else 'rejected'
            db.execute('UPDATE listings SET status=? WHERE id=?', (status, listing_id))
            db.execute('INSERT INTO reviews(listing_id,action,reason) VALUES (?,?,?)',
                       (listing_id, request.action, request.reason))
            return {'listing_id': listing_id, 'status': status}

    @app.post('/events', dependencies=[Depends(authenticate(bridge_key))])
    def event(event: Event):
        if event.is_self or event.thread_type != 'private':
            return {'ignored': True, 'reply': ''}
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            identity = (event.community_id, event.sender_id, event.event_id)
            cached = db.execute('SELECT response FROM events WHERE community_id=? AND sender_id=? AND event_id=?', identity).fetchone()
            if cached:
                return json.loads(cached['response'])
            text = event.text.strip()
            command, _, body = text.partition(' ')
            command = normalize(command)
            body = body.strip()
            if command == 'ban':
                parts = [p.strip() for p in body.split('|')]
                if len(parts) != 3 or not all(parts) or not parts[1].isascii() or not parts[1].isdigit():
                    raise HTTPException(422, 'Dùng: ban Tên món | Giá nguyên VND | Tình trạng')
                title, price, condition = parts
                if len(title) > 250 or len(condition) > 500 or not 0 <= int(price) <= 1_000_000_000:
                    raise HTTPException(422, 'Tên, tình trạng hoặc giá vượt giới hạn')
                id = 'NM-' + uuid4().hex[:12].upper()
                db.execute('INSERT INTO listings(id,community_id,seller_id,title,price_vnd,condition,status) VALUES (?,?,?,?,?,?,?)',
                           (id, event.community_id, event.sender_id, title, int(price), condition, 'draft'))
                result = {'listing_id': id, 'status': 'draft',
                          'reply': f'Bản nháp {id}: {title}, {int(price):,}đ, {condition}. Nhắn xacnhan {id} để gửi BQL duyệt.'}
            elif command in ('xacnhan', 'daban'):
                row = db.execute('SELECT * FROM listings WHERE id=? AND community_id=? AND seller_id=?',
                                 (body, event.community_id, event.sender_id)).fetchone()
                if not row:
                    raise HTTPException(404, 'Listing not found')
                required, status = ('draft', 'pending') if command == 'xacnhan' else ('approved', 'sold')
                if row['status'] != required:
                    raise HTTPException(409, 'Listing is not in the required state')
                db.execute('UPDATE listings SET status=? WHERE id=?', (status, body))
                result = {'listing_id': body, 'status': status,
                          'reply': 'Đã gửi BQL duyệt.' if status == 'pending' else 'Đã đánh dấu bán xong.'}
            elif command == 'tim':
                terms = normalize(body).split()
                if not terms:
                    raise HTTPException(422, 'Nhập từ khóa sau tim')
                rows = db.execute("SELECT id,title,price_vnd,condition FROM listings WHERE community_id=? AND status='approved' ORDER BY rowid DESC", (event.community_id,))
                found = [dict(r) for r in rows if all(term in normalize(r['title'] + ' ' + r['condition']) for term in terms)][:5]
                result = {'listings': found, 'reply': '\n'.join(f"{r['id']} — {r['title']} — {r['price_vnd']:,}đ" for r in found) or 'Chưa có tin phù hợp đã được duyệt.'}
            else:
                result = {'reply': 'Bạn có thể nhắn: ban Tên món | Giá VND | Tình trạng; tim từ khóa; xacnhan MÃ_TIN; daban MÃ_TIN. Đây là luồng nghiệp vụ thử nghiệm, chưa xử lý ảnh hoặc AI tự do.'}
            db.execute('INSERT INTO events VALUES (?,?,?,?)', (*identity, json.dumps(result, ensure_ascii=False)))
            return result

    return app


def from_environment():
    return create_app(os.getenv('DATABASE_PATH', 'private/market.db'),
                      os.environ['BRIDGE_API_KEY'], os.environ['ADMIN_API_KEY'])
