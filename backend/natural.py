"""Persist one active draft per trusted sender/community. No model call under DB write lock."""
import json
import threading
import sqlite3
import time
from uuid import uuid4
from fastapi import HTTPException
from backend.ai_text import AIUnavailable, ListingPatch

FIELDS = ('title', 'price_vnd', 'condition')
QUESTIONS = {'title': 'Bạn muốn bán món đồ gì?', 'price_vnd': 'Bạn muốn bán với giá bao nhiêu?',
             'condition': 'Món đồ đã dùng bao lâu, có hư hỏng gì không?'}
HELP = 'Bạn có thể nhắn: Mình muốn thanh lý ghế 500k. Nếu muốn đổi món, nhắn huy nhap trước. Tìm mua hiện dùng: tim từ khóa.'


class NaturalIntake:
    def __init__(self, database, extractor):
        self.database, self.extractor = database, extractor
        self._guard = threading.Lock()
        self._active = set()
        self._invalidated = set()

    def invalidate(self, scope):
        with self._guard:
            if scope in self._active:
                self._invalidated.add(scope)

    def handle(self, event):
        scope = (event.community_id, event.sender_id)
        with self._guard:
            if scope in self._active:
                raise HTTPException(409, 'Tin trước đang được xử lý. Bạn chờ phản hồi rồi gửi tiếp nhé.')
            self._active.add(scope)
        try:
            return self._handle(event, scope)
        except sqlite3.OperationalError:
            raise HTTPException(503, 'Dữ liệu đang bận. Bạn chờ một chút rồi thử lại nhé.') from None
        finally:
            with self._guard:
                self._active.remove(scope)
                self._invalidated.discard(scope)

    def _handle(self, event, scope):
        deadline = time.monotonic() + 11
        identity = (*scope, event.event_id)
        with self.database(timeout=.2) as db:
            db.execute('BEGIN')
            cached = db.execute('SELECT response FROM events WHERE community_id=? AND sender_id=? AND event_id=?', identity).fetchone()
            if cached:
                return json.loads(cached['response'])
            snapshot = db.execute('SELECT * FROM conversations WHERE community_id=? AND sender_id=?', scope).fetchone()
            epoch_row = db.execute('SELECT epoch FROM draft_epochs WHERE community_id=? AND sender_id=?', scope).fetchone()
            epoch = epoch_row['epoch'] if epoch_row else 0
            previous = json.loads(snapshot['data']) if snapshot else {}
        try:
            patch = self.extractor.extract(event.text, previous)
            patch = ListingPatch.model_validate(patch.model_dump())
        except (AIUnavailable, ValueError):
            raise HTTPException(503, 'AI tạm thời không xử lý được. Bạn thử lại hoặc dùng: ban Tên món | Giá VND | Tình trạng.') from None

        if time.monotonic() > deadline - .5:
            raise HTTPException(503, 'Xử lý quá thời gian. Bạn thử lại sau nhé.')
        with self._guard:
            if scope in self._invalidated:
                raise HTTPException(409, 'Bản nháp đã được hủy hoặc thay thế trong lúc AI xử lý.')
        with self.database(timeout=.2) as db:
            db.execute('BEGIN IMMEDIATE')
            cached = db.execute('SELECT response FROM events WHERE community_id=? AND sender_id=? AND event_id=?', identity).fetchone()
            if cached:
                return json.loads(cached['response'])
            current = db.execute('SELECT * FROM conversations WHERE community_id=? AND sender_id=?', scope).fetchone()
            current_epoch_row = db.execute('SELECT epoch FROM draft_epochs WHERE community_id=? AND sender_id=?', scope).fetchone()
            current_epoch = current_epoch_row['epoch'] if current_epoch_row else 0
            version = lambda row: (row['listing_id'], row['revision']) if row else None
            if current_epoch != epoch or version(current) != version(snapshot):
                raise HTTPException(409, 'Bản nháp vừa thay đổi. Bạn gửi lại yêu cầu sau khi xem phản hồi mới nhé.')
            if patch.intent == 'other':
                result = {'reply': HELP}
            else:
                values = dict(previous)
                for key in FIELDS:
                    if getattr(patch, key) is not None:
                        values[key] = getattr(patch, key)
                missing = [key for key in FIELDS if values.get(key) is None]
                id = snapshot['listing_id'] if snapshot else 'NM-' + uuid4().hex[:12].upper()
                revision = snapshot['revision'] + 1 if snapshot else 1
                # An existing complete draft may only remain editable while still draft.
                row = db.execute('SELECT status FROM listings WHERE id=?', (id,)).fetchone()
                if row and row['status'] != 'draft':
                    raise HTTPException(409, 'Tin đã chuyển trạng thái; không thể sửa bản đã gửi duyệt.')
                db.execute('INSERT INTO conversations(community_id,sender_id,listing_id,data,revision) VALUES (?,?,?,?,?) '
                           'ON CONFLICT(community_id,sender_id) DO UPDATE SET listing_id=excluded.listing_id,data=excluded.data,revision=excluded.revision',
                           (*scope, id, json.dumps(values, ensure_ascii=False), revision))
                db.execute('INSERT INTO current_drafts VALUES (?,?,?) ON CONFLICT(community_id,sender_id) DO UPDATE SET listing_id=excluded.listing_id',
                           (*scope, id))
                if missing:
                    result = {'listing_id': id, 'status': 'incomplete', 'missing_fields': missing, 'reply': QUESTIONS[missing[0]]}
                else:
                    db.execute('INSERT INTO listings(id,community_id,seller_id,title,price_vnd,condition,status) VALUES (?,?,?,?,?,?,?) '
                               'ON CONFLICT(id) DO UPDATE SET title=excluded.title,price_vnd=excluded.price_vnd,condition=excluded.condition',
                               (id, *scope, values['title'], values['price_vnd'], values['condition'], 'draft'))
                    result = {'listing_id': id, 'status': 'draft', 'missing_fields': [],
                              'reply': f"Bản nháp:\n{values['title']}\nGiá: {values['price_vnd']:,}đ\nTình trạng: {values['condition']}\nMã tin:\n{id}\n"
                                       "Bạn kiểm tra và nhắn xác nhận để gửi BQL duyệt. Muốn bỏ bản nháp, nhắn huy nhap."}
            if time.monotonic() > deadline - .5:
                raise HTTPException(503, 'Xử lý quá thời gian. Bạn thử lại sau nhé.')
            db.execute('INSERT INTO events VALUES (?,?,?,?)', (*identity, json.dumps(result, ensure_ascii=False)))
            return result
