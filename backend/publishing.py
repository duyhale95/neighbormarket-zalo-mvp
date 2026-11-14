"""Local group outbox. Unknown delivery is never retried automatically."""
import hmac
import re
import time
from uuid import uuid4
from pathlib import Path
from fastapi import Depends, HTTPException, Header
from pydantic import BaseModel, Field
from backend.messages import group_message, sold_message


class QueueRequest(BaseModel):
    community_id: str = Field(min_length=1, max_length=100)
    retry_uncertain: bool = False


class Receipt(BaseModel):
    token: str = Field(min_length=1, max_length=100)
    message_id: str = Field(pattern=r'^[0-9]{1,100}$')


def public_text(value):
    value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[ẩn email]', value)
    return re.sub(r'(?<!\d)(?:\+?84|0)(?:[ .()-]*\d){9,10}(?!\d)', '[ẩn SĐT]', value)


def format_post(row):
    return group_message({**dict(row),'title':public_text(row['title']),'condition':public_text(row['condition'])})


class GroupPublisher:
    def __init__(self, database, target, media_dir):
        self.database = database
        self.media_dir = Path(media_dir).resolve()
        if target and (not re.fullmatch(r'[0-9]{1,100}', target.get('group_id', ''))
                       or not target.get('community_id') or not target.get('group_name')):
            raise ValueError('Invalid group target')
        self.target = target
        with database() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS group_posts (
                    id TEXT PRIMARY KEY, listing_id TEXT NOT NULL, community_id TEXT NOT NULL,
                    group_id TEXT NOT NULL, group_name TEXT NOT NULL, part TEXT NOT NULL,
                    status TEXT NOT NULL, token TEXT, lease_until REAL, message_id TEXT, image_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(listing_id,group_id,part)
                );
                CREATE INDEX IF NOT EXISTS group_posts_queue ON group_posts(group_id,status);
            ''')
            if 'image_id' not in [r[1] for r in db.execute('PRAGMA table_info(group_posts)')]:
                db.execute('ALTER TABLE group_posts ADD COLUMN image_id TEXT')

    def enqueue(self, db, listing):
        if not self.target or listing['community_id'] != self.target['community_id']:
            return
        if listing['status'] != 'approved':
            raise HTTPException(409, 'Chỉ đăng nhóm khi tin đã được duyệt và còn bán.')
        photos = list(db.execute('SELECT id FROM listing_images WHERE listing_id=? AND community_id=? ORDER BY rowid',
                                (listing['id'],listing['community_id'])))
        group_id = self.target['group_id']
        existing = db.execute("SELECT status,image_id FROM group_posts WHERE listing_id=? AND group_id=? AND part='post'",
                              (listing['id'],group_id)).fetchone()
        cover = existing['image_id'] if existing else None
        existing_extra = db.execute("SELECT 1 FROM group_posts WHERE listing_id=? AND group_id=? AND part LIKE 'image_%' LIMIT 1",
                                    (listing['id'],group_id)).fetchone()
        if photos and (not existing or existing['status']=='queued') and (cover or not existing_extra):
            cover = photos[0]['id']
        jobs = [('post',cover)] + [('image_'+photo['id'],photo['id']) for photo in photos if photo['id']!=cover] + [('code',None)]
        for part,image_id in jobs:
            db.execute('INSERT OR IGNORE INTO group_posts(id,listing_id,community_id,group_id,group_name,part,status,image_id) '
                       'VALUES (?,?,?,?,?,?,?,?)', (uuid4().hex, listing['id'], listing['community_id'],
                       group_id, self.target['group_name'], part, 'queued',image_id))
        if cover:
            db.execute("UPDATE group_posts SET image_id=? WHERE listing_id=? AND group_id=? AND part='post' AND status='queued'",
                       (cover,listing['id'],group_id))

    def decorate(self, db, row):
        result = dict(row)
        configured = self.target and row['community_id'] == self.target['community_id']
        jobs = list(db.execute('SELECT part,status,image_id FROM group_posts WHERE listing_id=? AND group_id=?',
                              (row['id'], self.target['group_id']))) if configured else []
        states = [r['status'] for r in jobs if r['part'] != 'sold']
        sold_states = [r['status'] for r in jobs if r['part'] == 'sold']
        if not configured: status = 'not_configured'
        elif not states: status = 'not_queued'
        elif 'uncertain' in states: status = 'uncertain'
        elif 'sending' in states: status = 'sending'
        elif states and all(s == 'posted' for s in states): status = 'posted'
        elif 'cancelled' in states: status = 'cancelled'
        else: status = 'queued'
        result.update(publication_status=status, publication_group=self.target['group_name'] if configured else None)
        result['sold_publication_status'] = sold_states[0] if sold_states else 'not_needed'
        scheduled={job['image_id'] for job in jobs if job['image_id'] and job['status']!='cancelled'}
        photos=[r['id'] for r in db.execute('SELECT id FROM listing_images WHERE listing_id=?',(row['id'],))]
        result['unpublished_image_count']=sum(id not in scheduled for id in photos) if configured else 0
        if row['status'] == 'approved':
            result['publication_preview'] = format_post(row)
        return result

    def enqueue_sold(self, db, listing):
        if not self.target or listing['community_id'] != self.target['community_id']:
            return
        prior = db.execute("SELECT 1 FROM group_posts WHERE listing_id=? AND group_id=? AND part='post' AND status IN ('posted','sending','uncertain')",
                           (listing['id'], self.target['group_id'])).fetchone()
        db.execute("UPDATE group_posts SET status='cancelled' WHERE listing_id=? AND status='queued' AND part!='sold'", (listing['id'],))
        if prior:
            db.execute('INSERT OR IGNORE INTO group_posts(id,listing_id,community_id,group_id,group_name,part,status) VALUES (?,?,?,?,?,?,?)',
                       (uuid4().hex, listing['id'], listing['community_id'], self.target['group_id'], self.target['group_name'], 'sold', 'queued'))
        return bool(prior)

    def install(self, app, authenticate, bridge_key, admin_key):
        @app.post('/group-publications/claim', dependencies=[Depends(authenticate(bridge_key))])
        def claim(x_publisher_version: str = Header(default='1')):
            if not self.target:
                return {'ready': False}
            with self.database() as db:
                db.execute('BEGIN IMMEDIATE')
                now = time.time()
                db.execute("UPDATE group_posts SET status='uncertain' WHERE status='sending' AND lease_until<=?", (now,))
                db.execute("UPDATE group_posts SET status='cancelled' WHERE status='queued' AND "
                           "((part!='sold' AND listing_id IN (SELECT id FROM listings WHERE status!='approved')) OR "
                           "(part='sold' AND listing_id IN (SELECT id FROM listings WHERE status!='sold')))")
                group_id = self.target['group_id']
                if db.execute("SELECT 1 FROM group_posts WHERE group_id=? AND status='sending' LIMIT 1", (group_id,)).fetchone():
                    return {'ready': False}
                # Reconcile approved jobs queued before image support was installed.
                pending = list(db.execute("SELECT DISTINCT l.* FROM listings l JOIN group_posts p ON p.listing_id=l.id "
                                          "WHERE l.status='approved' AND p.status='queued' AND p.group_id=? AND l.community_id=?",
                                          (group_id,self.target['community_id'])))
                for listing in pending:
                    self.enqueue(db,listing)
                job = db.execute("SELECT p.* FROM group_posts p JOIN listings l ON l.id=p.listing_id "
                                 "WHERE p.group_id=? AND p.community_id=? AND p.status='queued' "
                                 "AND ((p.part='sold' AND l.status='sold') OR (p.part!='sold' AND l.status='approved')) "
                                 "AND (p.part IN ('post','sold') OR (EXISTS (SELECT 1 FROM group_posts prior WHERE prior.listing_id=p.listing_id "
                                 "AND prior.group_id=p.group_id AND prior.part='post' AND prior.status='posted') "
                                 "AND (p.part!='code' OR NOT EXISTS (SELECT 1 FROM group_posts photo WHERE photo.listing_id=p.listing_id "
                                 "AND photo.group_id=p.group_id AND photo.part LIKE 'image_%' AND photo.status NOT IN ('posted','cancelled'))))) "
                                 "ORDER BY p.rowid LIMIT 1", (group_id, self.target['community_id'])).fetchone()
                if not job:
                    return {'ready': False}
                row = db.execute('SELECT * FROM listings WHERE id=?', (job['listing_id'],)).fetchone()
                image_path = ''
                if job['image_id']:
                    if x_publisher_version != '2':
                        return {'ready':False,'reason':'workflow_update_required'}
                    photo = db.execute('SELECT data FROM listing_images WHERE id=? AND listing_id=? AND community_id=?',
                                       (job['image_id'],row['id'],row['community_id'])).fetchone()
                    if not photo or not re.fullmatch(r'[a-f0-9]{32}',job['image_id']):
                        raise HTTPException(409,'Không tìm thấy ảnh đã duyệt của món này.')
                    self.media_dir.mkdir(parents=True,exist_ok=True)
                    path = self.media_dir/(job['image_id']+'.jpg')
                    path.write_bytes(photo['data'])
                    image_path = str(path)
                token = uuid4().hex
                db.execute("UPDATE group_posts SET status='sending',token=?,lease_until=? WHERE id=?", (token, now+180, job['id']))
                return {'ready': True, 'job_id': job['id'], 'token': token, 'part': job['part'],
                        'group_id': group_id, 'group_name': job['group_name'], 'listing_id': row['id'],
                        'has_image':bool(image_path),'image_path':image_path,
                        'message': (sold_message({**dict(row),'title':public_text(row['title']),'condition':public_text(row['condition'])},group=True)
                                    if job['part'] == 'sold' else format_post(row) if job['part'] == 'post' else
                                    f"📷 Ảnh món đồ: {public_text(row['title'])}\nMã món đồ:\n{row['id']}" if job['image_id'] else row['id'])}

        @app.post('/group-publications/{job_id}/ack', dependencies=[Depends(authenticate(bridge_key))])
        def ack(job_id: str, request: Receipt):
            with self.database() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT * FROM group_posts WHERE id=?', (job_id,)).fetchone()
                if not row:
                    raise HTTPException(404, 'Publication not found')
                if not row['token'] or not hmac.compare_digest(row['token'], request.token):
                    raise HTTPException(409, 'Invalid delivery token')
                if row['status'] == 'posted':
                    if row['message_id'] != request.message_id:
                        raise HTTPException(409, 'Receipt differs from saved message')
                    return {'status': 'posted'}
                if row['status'] not in ('sending', 'uncertain'):
                    raise HTTPException(409, 'Publication not awaiting receipt')
                db.execute("UPDATE group_posts SET status='posted',message_id=?,lease_until=NULL WHERE id=?",
                           (request.message_id, job_id))
                return {'status': 'posted'}

        @app.post('/listings/{listing_id}/publish', dependencies=[Depends(authenticate(admin_key))])
        def queue(listing_id: str, request: QueueRequest):
            with self.database() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT * FROM listings WHERE id=? AND community_id=?', (listing_id, request.community_id)).fetchone()
                if not row:
                    raise HTTPException(404, 'Listing not found')
                if row['status'] not in ('approved', 'sold'):
                    raise HTTPException(409, 'Tin chưa được duyệt hoặc không còn bán.')
                if not self.target or request.community_id != self.target['community_id']:
                    raise HTTPException(409, 'Chưa cấu hình nhóm cho khu này.')
                if row['status'] == 'sold':
                    if not self.enqueue_sold(db, row):
                        raise HTTPException(409, 'Tin chưa từng được đăng nhóm; không cần thông báo đã bán.')
                else:
                    self.enqueue(db, row)
                if request.retry_uncertain:
                    db.execute("UPDATE group_posts SET status='queued',token=NULL,lease_until=NULL WHERE listing_id=? AND group_id=? AND status='uncertain' "
                               "AND ((?='sold' AND part='sold') OR (?='approved' AND part!='sold'))",
                               (listing_id, self.target['group_id'], row['status'], row['status']))
                return self.decorate(db, row)
