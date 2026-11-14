"""Local MVP. Only the trusted bridge may assert community/sender identity."""
import hmac
import json
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
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
    image_reviewed: bool = False
    image_review_token: str | None = Field(default=None, max_length=128)


def normalize(value):
    value = unicodedata.normalize('NFD', value.casefold().replace('đ', 'd'))
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn')


def parse_command(text):
    sold = re.fullmatch(r'da\s*ban(?:\s+(nm-[a-z0-9]+))?', ' '.join(normalize(text).split()))
    if sold:
        return 'daban', (sold.group(1) or '').upper()
    code = re.fullmatch(r'(?:xem\s+)?(nm-[a-z0-9]+)', ' '.join(normalize(text).split()))
    if code:
        return 'xem', code.group(1).upper()
    match = re.fullmatch(r'xac\s*nhan(?:\s+(nm-[a-z0-9]+))?', ' '.join(normalize(text).split()))
    if match:
        return 'xacnhan', (match.group(1) or '').upper()
    command, _, body = text.strip().partition(' ')
    return normalize(command), body.strip()


def create_app(db_path, bridge_key, admin_key, extractor=None, group_target=None, moderator=None):
    if not bridge_key or not admin_key or bridge_key == admin_key:
        raise ValueError('Configure two different nonempty API keys')
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def database(timeout=15):
        db = sqlite3.connect(db_path, timeout=timeout)
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
            CREATE TABLE IF NOT EXISTS conversations (
                community_id TEXT NOT NULL, sender_id TEXT NOT NULL, listing_id TEXT NOT NULL,
                data TEXT NOT NULL, revision INTEGER NOT NULL,
                PRIMARY KEY(community_id,sender_id)
            );
            CREATE TABLE IF NOT EXISTS draft_epochs (
                community_id TEXT NOT NULL, sender_id TEXT NOT NULL, epoch INTEGER NOT NULL,
                PRIMARY KEY(community_id,sender_id)
            );
            CREATE TABLE IF NOT EXISTS current_drafts (
                community_id TEXT NOT NULL, sender_id TEXT NOT NULL, listing_id TEXT NOT NULL,
                PRIMARY KEY(community_id,sender_id)
            );
        ''')

    app = FastAPI(title='NeighborMarket local MVP', version='0.1.0')
    from backend.natural import NaturalIntake
    intake = NaturalIntake(database, extractor) if extractor else None
    from backend.publishing import GroupPublisher
    publisher = GroupPublisher(database, group_target)
    from backend.images import ImageStore
    images = ImageStore(database, moderator)

    def authenticate(expected):
        def check(x_api_key: str = Header(default='')):
            if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
                raise HTTPException(401, 'Invalid API key')
        return check

    publisher.install(app, authenticate, bridge_key, admin_key)
    images.install(app, authenticate, bridge_key, admin_key)

    @app.get('/health')
    def health():
        return {'status': 'ok', 'mode': 'local-mvp', 'natural_text_enabled': intake is not None}

    @app.get('/admin', include_in_schema=False)
    def admin_page():
        return FileResponse(Path(__file__).parent / 'static' / 'admin.html', headers={'Cache-Control':'no-store'})

    @app.get('/listings', dependencies=[Depends(authenticate(admin_key))])
    def listings(community_id: str = Query(min_length=1, max_length=100)):
        with database() as db:
            # Bind displayed fields/images and the approval token to one snapshot.
            db.execute('BEGIN')
            return [{**publisher.decorate(db, row), 'images': images.metadata(db, row['id']), 'image_review_token': images.review_token(db,row['id'])} for row in db.execute(
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
            if status == 'approved':
                images.guard(db, listing_id, request.image_reviewed, request.reason, request.image_review_token)
            db.execute('UPDATE listings SET status=? WHERE id=?', (status, listing_id))
            db.execute('INSERT INTO reviews(listing_id,action,reason) VALUES (?,?,?)',
                       (listing_id, request.action, request.reason))
            if status == 'approved':
                publisher.enqueue(db, {**dict(row), 'status': status})
            return {'listing_id': listing_id, 'status': status}

    @app.post('/events', dependencies=[Depends(authenticate(bridge_key))])
    def event(event: Event):
        if event.is_self or event.thread_type != 'private':
            return {'ignored': True, 'reply': ''}
        text = event.text.strip()
        command, body = parse_command(text)
        cancelling = normalize(text) == 'huy nhap'
        deterministic = command in ('xacnhan', 'daban', 'tim', 'xem') or (command == 'ban' and '|' in body) or cancelling
        if intake and not deterministic:
            return intake.handle(event)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            identity = (event.community_id, event.sender_id, event.event_id)
            cached = db.execute('SELECT response FROM events WHERE community_id=? AND sender_id=? AND event_id=?', identity).fetchone()
            if cached:
                return json.loads(cached['response'])
            if cancelling:
                if intake:
                    intake.invalidate((event.community_id, event.sender_id))
                db.execute('INSERT INTO draft_epochs VALUES (?,?,1) ON CONFLICT(community_id,sender_id) DO UPDATE SET epoch=epoch+1',
                           (event.community_id, event.sender_id))
                previous = db.execute('SELECT listing_id FROM conversations WHERE community_id=? AND sender_id=?',
                                      (event.community_id, event.sender_id)).fetchone()
                if not previous:
                    previous = db.execute('SELECT listing_id FROM current_drafts WHERE community_id=? AND sender_id=?',
                                          (event.community_id, event.sender_id)).fetchone()
                if previous:
                    db.execute("UPDATE listings SET status='cancelled' WHERE id=? AND community_id=? AND seller_id=? AND status='draft'",
                               (previous['listing_id'], event.community_id, event.sender_id))
                db.execute('DELETE FROM conversations WHERE community_id=? AND sender_id=?', (event.community_id, event.sender_id))
                db.execute('DELETE FROM current_drafts WHERE community_id=? AND sender_id=?', (event.community_id, event.sender_id))
                result = {'reply': 'Đã hủy bản nháp hoặc yêu cầu tạo nháp đang xử lý (nếu có). Bạn có thể gửi thông tin món mới.'}
            elif command == 'ban':
                parts = [p.strip() for p in body.split('|')]
                if len(parts) != 3 or not all(parts) or not parts[1].isascii() or not parts[1].isdigit():
                    raise HTTPException(422, 'Dùng: ban Tên món | Giá nguyên VND | Tình trạng')
                title, price, condition = parts
                if len(title) > 250 or len(condition) > 500 or not 0 <= int(price) <= 1_000_000_000:
                    raise HTTPException(422, 'Tên, tình trạng hoặc giá vượt giới hạn')
                id = 'NM-' + uuid4().hex[:12].upper()
                db.execute('INSERT INTO listings(id,community_id,seller_id,title,price_vnd,condition,status) VALUES (?,?,?,?,?,?,?)',
                           (id, event.community_id, event.sender_id, title, int(price), condition, 'draft'))
                db.execute('DELETE FROM conversations WHERE community_id=? AND sender_id=?',
                           (event.community_id, event.sender_id))
                db.execute('INSERT INTO draft_epochs VALUES (?,?,1) ON CONFLICT(community_id,sender_id) DO UPDATE SET epoch=epoch+1',
                           (event.community_id, event.sender_id))
                db.execute('INSERT INTO current_drafts VALUES (?,?,?) ON CONFLICT(community_id,sender_id) DO UPDATE SET listing_id=excluded.listing_id',
                           (event.community_id, event.sender_id, id))
                result = {'listing_id': id, 'status': 'draft',
                          'reply': f'Bản nháp:\n{title}\nGiá: {int(price):,}đ\nTình trạng: {condition}\nMã tin:\n{id}\nNhắn xác nhận để gửi BQL duyệt.'}
            elif command in ('xacnhan', 'daban'):
                if command == 'daban' and not body:
                    choices = list(db.execute("SELECT id,title FROM listings WHERE community_id=? AND seller_id=? AND status='approved' ORDER BY rowid DESC",
                                              (event.community_id, event.sender_id)))
                    if len(choices) != 1:
                        result = {'reply': ('Bạn muốn đánh dấu món nào đã bán? Nhắn daban MÃ_TIN:\n' + '\n'.join(f"{x['id']} — {x['title']}" for x in choices[:10])) if choices else 'Bạn chưa có tin đang bán để đánh dấu.'}
                        db.execute('INSERT INTO events VALUES (?,?,?,?)', (*identity, json.dumps(result, ensure_ascii=False)))
                        return result
                    body = choices[0]['id']
                if command == 'xacnhan' and not body:
                    current = db.execute('SELECT listing_id FROM conversations WHERE community_id=? AND sender_id=?',
                                         (event.community_id, event.sender_id)).fetchone()
                    if not current:
                        current = db.execute('SELECT listing_id FROM current_drafts WHERE community_id=? AND sender_id=?',
                                             (event.community_id, event.sender_id)).fetchone()
                    if not current:
                        raise HTTPException(409, 'Bạn chưa có bản nháp hiện tại. Nếu đã có mã tin, nhắn xác nhận MÃ_TIN.')
                    body = current['listing_id']
                row = db.execute('SELECT * FROM listings WHERE id=? AND community_id=? AND seller_id=?',
                                 (body, event.community_id, event.sender_id)).fetchone()
                if not row:
                    partial = db.execute('SELECT listing_id FROM conversations WHERE community_id=? AND sender_id=? AND listing_id=?',
                                         (event.community_id, event.sender_id, body)).fetchone()
                    if partial:
                        raise HTTPException(422, 'Bản nháp chưa đủ tên món, giá và tình trạng. Hãy bổ sung trước khi xác nhận.')
                    raise HTTPException(404, 'Listing not found')
                required, status = ('draft', 'pending') if command == 'xacnhan' else ('approved', 'sold')
                if row['status'] != required:
                    raise HTTPException(409, 'Listing is not in the required state')
                db.execute('UPDATE listings SET status=? WHERE id=?', (status, body))
                if status == 'sold':
                    publisher.enqueue_sold(db, {**dict(row), 'status': status})
                if command == 'xacnhan':
                    db.execute('DELETE FROM conversations WHERE community_id=? AND sender_id=? AND listing_id=?',
                               (event.community_id, event.sender_id, body))
                    db.execute('DELETE FROM current_drafts WHERE community_id=? AND sender_id=? AND listing_id=?',
                               (event.community_id, event.sender_id, body))
                result = {'listing_id': body, 'status': status,
                          'reply': f'Đã gửi BQL duyệt.\nMã tin:\n{body}' if status == 'pending' else 'Đã đánh dấu bán xong.'}
            elif command == 'xem':
                from backend.publishing import public_text
                row = db.execute("SELECT id,title,price_vnd,condition FROM listings WHERE id=? AND community_id=? AND status='approved'",
                                 (body, event.community_id)).fetchone()
                if row:
                    item = dict(row)
                    item['title'], item['condition'] = public_text(item['title']), public_text(item['condition'])
                    result = {'listings': [item], 'reply': f"{item['title']}\nGiá: {item['price_vnd']:,}đ\nTình trạng: {item['condition']}\nMã món đồ:\n{item['id']}"}
                else:
                    result = {'listings': [], 'reply': 'Tin này chưa được duyệt hoặc không còn bán. Nhắn tim từ khóa để tìm món khác.'}
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

    @app.post('/bridge/zalo', dependencies=[Depends(authenticate(bridge_key))])
    async def zalo_bridge(request: Request, x_sender_id: str = Header(min_length=1, max_length=100),
                          x_event_id: str = Header(min_length=1, max_length=200)):
        # Single demo community, configured by server; never parsed from chat content.
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 16000:
                raise HTTPException(413, 'Message too large')
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(422, 'Text must be UTF-8')
        if text.startswith('NM-TEXT:\n'):
            text = text[len('NM-TEXT:\n'):]
        if not text.strip() or len(text) > 4000:
            raise HTTPException(422, 'Text must contain 1 to 4000 characters')
        payload = Event(event_id=x_event_id, sender_id=x_sender_id,
                        community_id=os.getenv('DEMO_COMMUNITY_ID', 'demo'), text=text)
        try:
            return await run_in_threadpool(event, payload)
        except HTTPException as error:
            # Business errors become safe user-facing replies; auth never enters here.
            replies = {404:'Không tìm thấy tin thuộc quyền của bạn. Hãy kiểm tra mã tin.'}
            return {'business_status':error.status_code,
                    'reply':replies.get(error.status_code, str(error.detail))}

    return app


def from_environment():
    from backend.ai_text import GeminiTextExtractor
    key, model = os.getenv('GEMINI_API_KEY'), os.getenv('GEMINI_MODEL')
    extractor = GeminiTextExtractor(key, model) if key and model else None
    group_id = os.getenv('ZALO_GROUP_ID')
    target = {'group_id': group_id, 'group_name': os.getenv('ZALO_GROUP_NAME', 'Nhóm demo'),
              'community_id': os.getenv('DEMO_COMMUNITY_ID', 'demo')} if group_id else None
    from backend.images import OpenAIModerator
    return create_app(os.getenv('DATABASE_PATH', 'private/market.db'),
                      os.environ['BRIDGE_API_KEY'], os.environ['ADMIN_API_KEY'], extractor=extractor, group_target=target,
                      moderator=OpenAIModerator(os.getenv('OPENAI_API_KEY')))
