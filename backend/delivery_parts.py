"""Ordered immutable media snapshots below the existing listing_deliveries outbox.

No second queue, direct Zalo calls or retry of unknown outcomes. Main publishing.py
inspired cover/extra/code ordering; target IDs, auth and parent endpoints are kept.
"""
import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, Response


def listing_message(row) -> str:
    clean=lambda value:' '.join(value.split())
    return (f"NEIGHBORMARKET — TIN ĐÃ DUYỆT\n\nSản phẩm: {clean(row['title'])}\n"
            f"Giá: {row['price_vnd']:,}đ\nTình trạng: {clean(row['condition'])}\n\n"
            f"Mã tin: {row['id']}\n\nNhắn riêng cho Meo Meo để tìm hiểu sản phẩm.")


class DeliveryParts:
    def __init__(self, database, images, db_path, media_dir=None):
        self.database,self.images=database,images
        self.anchor=Path(db_path).resolve().parent
        self.root=Path(media_dir) if media_dir else self.anchor/'group-media'
        if not self.root.resolve().is_relative_to(self.anchor):
            raise ValueError('Media export must remain in the private database directory')
        with database() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS delivery_parts (
                id TEXT PRIMARY KEY,delivery_id TEXT NOT NULL,kind TEXT NOT NULL,position INTEGER NOT NULL,
                status TEXT NOT NULL,message TEXT NOT NULL,image_id TEXT,image_digest TEXT,
                snapshot_token TEXT NOT NULL,claim_token TEXT,lease_expires_at TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,sent_message_id TEXT,
                transport_mode TEXT NOT NULL DEFAULT 'unverified',
                UNIQUE(delivery_id,kind,position));
                CREATE INDEX IF NOT EXISTS parts_parent ON delivery_parts(delivery_id,position);
            ''')

    def has_parts(self, db, delivery_id: str) -> bool:
        return bool(db.execute('SELECT 1 FROM delivery_parts WHERE delivery_id=? LIMIT 1',(delivery_id,)).fetchone())

    def public(self, db, delivery_id: str) -> list[dict]:
        return [{k:r[k] for k in ('id','kind','position','status','attempts','last_error','sent_message_id','transport_mode')}
            for r in db.execute('SELECT * FROM delivery_parts WHERE delivery_id=? ORDER BY position',(delivery_id,))]

    def enqueue(self, db, delivery_id: str, listing) -> None:
        token=self.images.review_token(db,listing['id'])
        photos=list(db.execute('SELECT id,digest FROM listing_images WHERE listing_id=? ORDER BY rowid',(listing['id'],)))
        jobs=[('cover_photo_with_caption',listing_message(listing),photos[0]) if photos else ('post_text',listing_message(listing),None)]
        jobs += [('additional_photo',f"Ảnh sản phẩm {listing['id']}",p) for p in photos[1:]]
        jobs += [('listing_code',listing['id'],None)]
        for index,(kind,message,image) in enumerate(jobs):
            db.execute('INSERT OR IGNORE INTO delivery_parts(id,delivery_id,kind,position,status,message,image_id,image_digest,snapshot_token) VALUES (?,?,?,?,?,?,?,?,?)',
                (uuid4().hex,delivery_id,kind,index,'queued',message,image['id'] if image else None,image['digest'] if image else None,token))

    def enqueue_single(self, db, parent, listing) -> None:
        db.execute('INSERT OR IGNORE INTO delivery_parts(id,delivery_id,kind,position,status,message,snapshot_token) VALUES (?,?,?,?,?,?,?)',
            (uuid4().hex,parent['id'],'post_text',0,'queued',parent['message_snapshot'] or listing_message(listing),
             parent['snapshot_token'] or self.images.review_token(db,listing['id'])))

    def sync(self, db, delivery_id: str) -> str:
        states=[r[0] for r in db.execute('SELECT status FROM delivery_parts WHERE delivery_id=?',(delivery_id,))]
        if not states: return ''
        if 'unknown' in states: status='unknown'
        elif 'claimed' in states: status='claimed'
        elif 'failed' in states: status='failed'
        elif 'queued' in states: status='queued'
        elif 'sent' in states: status='sent'
        else: status='cancelled'
        db.execute('UPDATE listing_deliveries SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(status,delivery_id))
        return status

    def expire(self, db) -> None:
        parents=[r[0] for r in db.execute("SELECT DISTINCT delivery_id FROM delivery_parts WHERE status='claimed' AND lease_expires_at<=CURRENT_TIMESTAMP")]
        db.execute("UPDATE delivery_parts SET status='unknown',last_error='claim_expired' WHERE status='claimed' AND lease_expires_at<=CURRENT_TIMESTAMP")
        for parent in parents: self.sync(db,parent)

    def export(self, db, part) -> str:
        if not re.fullmatch(r'[a-f0-9]{32}',part['image_id'] or ''): raise ValueError('Invalid media ID')
        if not self.root.resolve().is_relative_to(self.anchor): raise ValueError('Unsafe media directory')
        self.root.mkdir(parents=True,exist_ok=True)
        path=self.root/(part['id']+'.jpg')
        if path.is_symlink() or not path.resolve().is_relative_to(self.anchor): raise ValueError('Unsafe media path')
        image=db.execute('SELECT data,digest FROM listing_images WHERE id=?',(part['image_id'],)).fetchone()
        if not image or image['digest']!=part['image_digest'] or hashlib.sha256(image['data']).hexdigest()!=part['image_digest']:
            raise ValueError('Image changed after approval')
        try:
            with path.open('xb') as stream: stream.write(image['data'])
        except FileExistsError:
            # Re-validate: the existing entry may have been swapped for a link meanwhile.
            if path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
                raise ValueError('Unsafe media path')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=part['image_digest']: raise ValueError('Export changed')
        resolved=path.resolve()
        if not resolved.is_relative_to(self.root.resolve()): raise ValueError('Unsafe media path')
        return str(resolved)

    def claim(self, db, parent, listing, version: str):
        if version!='2': return Response(status_code=204)
        part=db.execute("SELECT * FROM delivery_parts WHERE delivery_id=? AND status='queued' ORDER BY position LIMIT 1",(parent['id'],)).fetchone()
        if not part: return Response(status_code=204)
        if db.execute("SELECT 1 FROM delivery_parts WHERE delivery_id=? AND position<? AND status NOT IN ('sent','cancelled')",(parent['id'],part['position'])).fetchone():
            return Response(status_code=204)
        if part['kind']!='sold_notice' and not hmac.compare_digest(part['snapshot_token'],self.images.review_token(db,listing['id'])):
            db.execute("UPDATE delivery_parts SET status='failed',last_error='stale_snapshot' WHERE delivery_id=? AND status='queued'",(parent['id'],))
            self.sync(db,parent['id']); return Response(status_code=204)
        try: path=self.export(db,part) if part['image_id'] else ''
        except (ValueError,OSError):
            db.execute("UPDATE delivery_parts SET status='failed',last_error='unsafe_media' WHERE id=?",(part['id'],))
            self.sync(db,parent['id']); return Response(status_code=204)
        token=secrets.token_urlsafe(32)
        db.execute("UPDATE delivery_parts SET status='claimed',claim_token=?,lease_expires_at=datetime('now','+5 minutes'),attempts=attempts+1 WHERE id=?",(token,part['id']))
        db.execute("UPDATE listing_deliveries SET status='claimed',claim_token=?,lease_expires_at=datetime('now','+5 minutes'),attempts=attempts+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",(token,parent['id']))
        return {'delivery_id':parent['id'],'part_id':part['id'],'part_type':part['kind'],
            'claim_token':token,'group_id':parent['target_group_id'],'message':part['message'],
            'attempt':part['attempts']+1,'has_image':bool(path),'image_path':path}

    def require(self, db, delivery_id: str, part_id: str | None, token: str):
        row=db.execute('SELECT * FROM delivery_parts WHERE delivery_id=? AND id=?',(delivery_id,part_id)).fetchone()
        if not row or not row['claim_token'] or not hmac.compare_digest(row['claim_token'],token):
            raise HTTPException(409,'Invalid or stale part claim')
        return row

    def ack(self, db, delivery_id: str, request) -> dict:
        part=self.require(db,delivery_id,request.part_id,request.claim_token)
        if not request.sent_message_id or request.transport_mode=='unverified': raise HTTPException(422,'A part needs an explicit transport receipt')
        if part['status']=='sent' and part['sent_message_id']==request.sent_message_id:
            return {'delivery_id':delivery_id,'status':self.sync(db,delivery_id)}
        if part['status'] not in ('claimed','unknown'): raise HTTPException(409,'Part cannot be acknowledged')
        db.execute("UPDATE delivery_parts SET status='sent',sent_message_id=?,transport_mode=?,last_error=NULL,lease_expires_at=NULL WHERE id=?",
            (request.sent_message_id,request.transport_mode,part['id']))
        db.execute('UPDATE listing_deliveries SET sent_message_id=?,transport_mode=?,last_error=NULL WHERE id=?',(request.sent_message_id,request.transport_mode,delivery_id))
        return {'delivery_id':delivery_id,'status':self.sync(db,delivery_id)}

    def failure(self, db, delivery_id: str, request) -> dict:
        part=self.require(db,delivery_id,request.part_id,request.claim_token)
        if part['status']!='claimed': raise HTTPException(409,'Part no longer claimed')
        status='unknown' if request.outcome=='unknown' else 'failed'
        error=request.error if request.error in ('timeout','connection_error','send_rejected') else 'other'
        db.execute('UPDATE delivery_parts SET status=?,last_error=?,transport_mode=? WHERE id=?',(status,error,request.transport_mode,part['id']))
        db.execute('UPDATE listing_deliveries SET last_error=?,transport_mode=? WHERE id=?',(error,request.transport_mode,delivery_id))
        return {'delivery_id':delivery_id,'status':self.sync(db,delivery_id)}

    def reconcile(self, db, delivery_id: str, request) -> dict:
        # BQL must name the exact part it verified; a parent-level decision is ambiguous.
        if not request.part_id: raise HTTPException(422,'Multipart delivery: record the part_id that was verified')
        rows=list(db.execute("SELECT * FROM delivery_parts WHERE delivery_id=? AND status='unknown'",(delivery_id,)))
        if len(rows)!=1 or rows[0]['id']!=request.part_id: raise HTTPException(409,'No unique unknown part to reconcile')
        part=rows[0]; sent=request.decision=='sent'
        if sent and not request.sent_message_id: raise HTTPException(422,'Record the observed message ID for this part')
        db.execute("UPDATE delivery_parts SET status=?,sent_message_id=?,claim_token=NULL,transport_mode='manual',last_error=? WHERE id=?",
            ('sent' if sent else 'failed',request.sent_message_id if sent else None,None if sent else 'reconciled_not_sent',part['id']))
        db.execute('INSERT INTO delivery_reconciliations(delivery_id,decision,reason,part_id) VALUES (?,?,?,?)',(delivery_id,request.decision,request.reason,part['id']))
        db.execute("UPDATE listing_deliveries SET claim_token=NULL,transport_mode='manual' WHERE id=?",(delivery_id,))
        return {'delivery_id':delivery_id,'status':self.sync(db,delivery_id)}

    def sold(self, db, listing) -> None:
        parent=db.execute('SELECT * FROM listing_deliveries WHERE listing_id=?',(listing['id'],)).fetchone()
        if not parent: return
        receipt=db.execute("SELECT 1 FROM delivery_parts WHERE delivery_id=? AND kind IN ('post_text','cover_photo_with_caption') AND status='sent' AND sent_message_id IS NOT NULL",(parent['id'],)).fetchone()
        if not self.has_parts(db,parent['id']) and parent['status']=='sent' and parent['sent_message_id']:
            db.execute('INSERT INTO delivery_parts(id,delivery_id,kind,position,status,message,snapshot_token,sent_message_id,transport_mode) VALUES (?,?,?,?,?,?,?,?,?)',
                (uuid4().hex,parent['id'],'post_text',0,'sent',listing_message(listing),'legacy',parent['sent_message_id'],parent['transport_mode']))
            receipt=True
        db.execute("UPDATE delivery_parts SET status='cancelled',claim_token=NULL WHERE delivery_id=? AND status IN ('queued','failed')",(parent['id'],))
        if receipt:
            message=f"ĐÃ BÁN — NEIGHBORMARKET\nSản phẩm: {' '.join(listing['title'].split())}\nMã tin: {listing['id']}\nTin đã ngừng xuất hiện trong tìm kiếm."
            db.execute('INSERT OR IGNORE INTO delivery_parts(id,delivery_id,kind,position,status,message,snapshot_token) VALUES (?,?,?,?,?,?,?)',
                (uuid4().hex,parent['id'],'sold_notice',1000,'queued',message,'sold'))
        if self.has_parts(db,parent['id']): self.sync(db,parent['id'])
