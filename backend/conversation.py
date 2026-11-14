"""One persistent seller/community context inside the target SQLite database.

Draft UX adapted from VHR-07; revision-based stale-result guard inspired by
source B. No partner DB engine, model stub, direct publication or auto-approval.
"""
import json
import re
import sqlite3
import unicodedata
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from backend.ai import ListingExtraction
from backend.moderation import assess_listing
from backend.vnd import fold, parse_vnd
from backend.messages import draft_message

FIELDS=('title','price_vnd','condition')
LABELS={'title':'tên sản phẩm','price_vnd':'giá','condition':'tình trạng'}
HELP='Dạ, Meo Meo hỗ trợ đăng bán và tìm mua. Bạn có thể nhắn “Bán ghế còn tốt, 800k” hoặc “tìm ghế” ạ.'


def parse_action(text: str) -> tuple[str,str]:
    text=text.strip()
    normalized=' '.join(fold(text).split())
    if normalized.strip(' !.,?') in ('chao', 'xin chao', 'chao meo meo', 'hello', 'hi', 'cam on', 'cam on meo meo'):
        return 'greeting',''
    if normalized in ('huy nhap','huy ban nhap'): return 'huy',''
    if re.fullmatch(r'NM-[A-F0-9]{12}',text,re.I): return 'detail',text.upper()
    if normalized.strip(' !.,') in ('ok','xac nhan','xacnhan','xac nhan a','xac nhan nhe'):
        return 'xacnhan',''
    for phrase,action in [('xac nhan','xacnhan'),('da ban','daban'),
                           ('sua gia','edit_price'),('sua tieu de','edit_title'),
                           ('sua tinh trang','edit_condition')]:
        if normalized == phrase:
            return action,''
        if normalized.startswith(phrase + ' '):
            words=len(phrase.split())
            return action,text.split(maxsplit=words)[words].strip()
    parts=text.split(maxsplit=1)
    command=fold(parts[0]).lstrip('/') if parts else ''
    body=parts[1].strip() if len(parts)>1 else ''
    if command in ('xacnhan', 'daban', 'tim', 'huy') or (command == 'ban' and '|' in body):
        return command, body
    if command == 'ban' and (text.startswith('/') or parts[0].casefold() == 'ban'):
        return command, body
    return 'chat', text


def snapshot(db: sqlite3.Connection, scope: tuple[str,str]) -> dict[str, Any]:
    row=db.execute('SELECT * FROM conversations WHERE community_id=? AND sender_id=?',scope).fetchone()
    return {'revision':row['revision'],'listing_id':row['listing_id'],'data':json.loads(row['data'])} if row else {
        'revision':0,'listing_id':None,'data':{}}


def set_context(db: sqlite3.Connection, scope: tuple[str,str], listing_id: str | None, data: dict) -> None:
    db.execute('INSERT INTO conversations(community_id,sender_id,listing_id,data,revision) VALUES (?,?,?,?,1) '
               'ON CONFLICT(community_id,sender_id) DO UPDATE SET listing_id=excluded.listing_id, '
               'data=excluded.data,revision=conversations.revision+1',
               (*scope,listing_id,json.dumps(data,ensure_ascii=False)))


def clear_context(db: sqlite3.Connection, scope: tuple[str,str], listing_id: str | None = None) -> None:
    current=snapshot(db,scope)
    if listing_id is None or current['listing_id']==listing_id:
        set_context(db,scope,None,{})


def deterministic_patch(text: str, previous: dict) -> ListingExtraction | None:
    """Narrow offline patterns; copy source spans, never infer a price/condition."""
    original=unicodedata.normalize('NFC',text.strip())
    norm=fold(original)
    intent=re.search(r'\b(?:muon ban|can ban|minh ban|toi ban|thanh ly|nhuong lai)\s+(?:(?:chiec|cai|mot)\s+)?',norm)
    if intent is None and original.casefold().startswith('bán '):
        intent=re.match(r'ban\s+(?:(?:chiec|cai|mot)\s+)?',norm)
    spans=[]
    # Explicit currency units, or an explicit price label. Do not consume age/count.
    money=re.compile(r'(?<![\w.,-])\d+(?:[.,]\d+)*\s*(?:trieu|tr|nghin|ngan|k)'
                     r'(?:\s*\d{1,3}\s*(?:nghin|ngan|k)?)?(?:\s*(?:vnd|dong|d))?(?!\w)')
    labelled=re.compile(r'\bgia\s*[:=]?\s*(\d+(?:[.,]\d+)*(?:\s*(?:vnd|dong|d))?)\b')
    for match in money.finditer(norm):
        value=parse_vnd(match.group().strip('., '))
        if value is not None: spans.append((match.start(),match.end(),value))
    if not spans:
        for match in labelled.finditer(norm):
            value=parse_vnd(match.group(1))
            if value is not None: spans.append((match.start(),match.end(),value))
    if not spans and previous.get('values'):
        price=parse_vnd(original.strip('., '))
        if price is not None: spans=[(0,len(original),price)]
    price=spans[0][2] if len({s[2] for s in spans})==1 else None
    condition_match=re.search(
        r'\b(?:(?:khong|chua|chang)\s+(?:(?:he|tung|con|bi|duoc|phai)\s+){0,2})?'
        r'(?:da (?:su dung|dung)|dung(?: duoc)?|su dung|con tot|con moi|moi|cu|khong hu hong|hong)\b',norm)
    condition=None
    if condition_match:
        end=len(original)
        for start,_,_ in spans:
            if start>condition_match.start(): end=min(end,start)
        label=re.search(r'\bgia\b',norm[condition_match.start():])
        if label: end=min(end,condition_match.start()+label.start())
        condition=original[condition_match.start():end].strip(' ,.;') or None
    title=None
    if intent:
        end=len(original)
        for start,_,_ in spans: end=min(end,start)
        for cut in (re.search(r'\bgia\b',norm[intent.end():]),):
            if cut: end=min(end,intent.end()+cut.start())
        if condition_match and condition_match.start()>=intent.end(): end=min(end,condition_match.start())
        title=original[intent.end():end].strip(' ,.;') or None
    if not intent and not previous.get('values'):
        return None
    if not intent and price is None and condition is None:
        return None
    return ListingExtraction(intent='sell',title=title,price_vnd=price,condition=condition,
        missing_fields=[field for field,value in [('title',title),('price_vnd',price),('condition',condition)] if value is None],risk_flags=[])


def _save_complete(db: sqlite3.Connection, scope: tuple[str,str], listing_id: str, values: dict,
                   data: dict, source_channel: str) -> dict:
    title,price,condition=(values.get(field) for field in FIELDS)
    if not isinstance(title,str) or not isinstance(condition,str) or type(price) is not int:
        raise HTTPException(422,'Invalid listing fields')
    if not 1<=len(title)<=250 or not 1<=len(condition)<=500 or not 0<=price<=1_000_000_000:
        raise HTTPException(422,'Tên, tình trạng hoặc giá vượt giới hạn')
    report=assess_listing(title,condition,price,ai_flags=data.get('ai_flags',False),
                          model_version=data.get('model_version','rules-only'),
                          ai_status=data.get('ai_status','not_requested'))
    existing=db.execute('SELECT * FROM listings WHERE id=?',(listing_id,)).fetchone()
    if existing and (existing['community_id']!=scope[0] or existing['seller_id']!=scope[1] or existing['status']!='draft'):
        raise HTTPException(409,'Chỉ sửa bản nháp của bạn trước khi gửi BQL')
    db.execute('INSERT INTO listings(id,community_id,seller_id,title,price_vnd,condition,status,moderation_flags,moderation_report,source_channel) '
               'VALUES (?,?,?,?,?,?,\'draft\',?,?,?) ON CONFLICT(id) DO UPDATE SET '
               'title=excluded.title,price_vnd=excluded.price_vnd,condition=excluded.condition,'
               'moderation_flags=excluded.moderation_flags,moderation_report=excluded.moderation_report',
               (listing_id,*scope,title,price,condition,json.dumps(report.categories),report.model_dump_json(),source_channel))
    data['values']=values
    set_context(db,scope,listing_id,data)
    return {'listing_id':listing_id,'status':'draft','missing_fields':[],
        'reply':draft_message({'id':listing_id,**values})}


def draft_action(db: sqlite3.Connection, event: Any, command: str, body: str,
                 extracted: ListingExtraction | None, expected_revision: int, *,
                 ai_status: str = 'not_requested', model_version: str = 'rules-only') -> dict | None:
    scope=(event.community_id,event.sender_id)
    current=snapshot(db,scope)
    if command=='ban':
        parts=[p.strip() for p in body.split('|')]
        if len(parts)!=3 or not all(parts) or not parts[1].isascii() or not parts[1].isdigit():
            raise HTTPException(422,'Dùng: ban Tên món | Giá nguyên VND | Tình trạng')
        return _save_complete(db,scope,'NM-'+uuid4().hex[:12].upper(),dict(zip(FIELDS,[parts[0],int(parts[1]),parts[2]])),
                              {'ai_flags':False},event.source_channel)
    if command=='huy':
        lid=body or current['listing_id']
        if lid:
            row=db.execute('SELECT * FROM listings WHERE id=? AND community_id=? AND seller_id=?',(lid,*scope)).fetchone()
            if not row:
                raise HTTPException(404,'Listing not found')
            if row['status']!='draft': raise HTTPException(409,'Chỉ hủy được bản nháp chưa gửi duyệt')
            db.execute("UPDATE listings SET status='cancelled' WHERE id=?",(lid,))
            clear_context(db,scope,lid)
        else:
            clear_context(db,scope)
        return {'listing_id':lid,'status':'cancelled','reply':'Dạ, mình đã hủy bản nháp.'}
    if command in ('edit_price','edit_title','edit_condition'):
        if not current['data'].get('values'): raise HTTPException(409,'Không có bản nháp hiện tại để sửa')
        values=dict(current['data']['values'])
        if command=='edit_price':
            price=parse_vnd(body)
            if price is None: raise HTTPException(422,'Giá chưa rõ. Ví dụ: sửa giá 700k')
            values['price_vnd']=price
        elif command == 'edit_title':
            if not 1<=len(body)<=250: raise HTTPException(422,'Tiêu đề từ 1 đến 250 ký tự')
            values['title']=body
        else:
            if not 1<=len(body)<=500: raise HTTPException(422,'Tình trạng từ 1 đến 500 ký tự')
            values['condition']=body
        data={**current['data'],'values':values}
    elif extracted and extracted.intent=='sell':
        if current['revision']!=expected_revision:
            raise HTTPException(409,'Bản nháp vừa thay đổi. Xem phản hồi mới trước khi gửi lại.')
        values=dict(current['data'].get('values',{}))
        if values.get('title') and extracted.title and fold(extracted.title)!=fold(values['title']):
            raise HTTPException(409,'Muốn đổi món, hủy bản nháp trước hoặc dùng sửa tiêu đề.')
        for field in FIELDS:
            value=getattr(extracted,field)
            if value is not None: values[field]=value.strip() if isinstance(value,str) else value
        data={**current['data'],'values':values,'ai_flags':bool(extracted.risk_flags) or current['data'].get('ai_flags',False),
              'model_version':model_version,'ai_status':ai_status}
    else:
        return None
    missing=[field for field in FIELDS if values.get(field) is None or values.get(field)=='']
    if missing:
        set_context(db,scope,current['listing_id'],data)
        needed=', '.join(LABELS[field] for field in missing)
        return {'status':'incomplete','missing_fields':missing,
                'reply':f'Dạ, bạn cho mình thêm {needed} nhé.'}
    return _save_complete(db,scope,current['listing_id'] or 'NM-'+uuid4().hex[:12].upper(),values,data,event.source_channel)
