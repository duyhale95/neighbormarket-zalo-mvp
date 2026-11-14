"""Synthetic image -> BQL evidence -> ordered photos/code -> sold notice. NO Zalo."""
import base64
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
from backend.app import create_app
from backend.channels import MockZaloTransport
from backend.publisher import Publisher


class SyntheticModerator:
    def check(self, data, mime, text):
        return {'status':'clear','categories':[],'model':'SYNTHETIC-MOCK-NOT-OPENAI'}


def run_demo() -> dict:
    with tempfile.TemporaryDirectory(prefix='nm-media-demo-') as directory,patch.dict('os.environ',{'AI_ENABLED':'false','IMAGE_MODERATION_ENABLED':'false'}):
        with TestClient(create_app(Path(directory)/'market.db','demo-bridge','demo-admin',target_group_id='mock-group',
                publication_mode='photos_v2',image_moderator=SyntheticModerator())) as client:
            admin={'X-API-Key':'demo-admin'};bridge={'X-API-Key':'demo-bridge'};seq=0
            def event(text,sender='seller'):
                nonlocal seq
                seq+=1
                response=client.post('/events',headers=bridge,json={'event_id':str(seq),'community_id':'demo','sender_id':sender,'text':text})
                response.raise_for_status();return response.json()
            listing=event('Mình muốn bán chiếc ghế công thái học, giá 800k, dùng 6 tháng.')['listing_id']
            for color in ('gold','navy'):
                stream=io.BytesIO();Image.new('RGB',(60,40),color).save(stream,format='PNG')
                client.post(f'/listings/{listing}/images',headers=admin,json={'community_id':'demo','image_base64':base64.b64encode(stream.getvalue()).decode()}).raise_for_status()
            event('ok')
            row=client.get('/listings?community_id=demo',headers=admin).json()[0]
            client.post(f'/listings/{listing}/review',headers=admin,json={'community_id':'demo','action':'approve',
                'reason':'Đã xem ảnh màu tổng hợp, chỉ demo giả lập','image_review_token':row['image_review_token']}).raise_for_status()
            transport=MockZaloTransport('303','mock-group');worker=Publisher(client,'demo-bridge',transport,'mock-group')
            for _ in range(3): assert worker.process_once().status=='sent'
            assert worker.process_once().status=='idle'
            assert listing in event('tìm ghế',sender='buyer')['reply']
            event('daban '+listing)
            assert worker.process_once().status=='sent' and worker.process_once().status=='idle'
            assert not event('tìm ghế',sender='buyer')['listings']
            job=client.get('/deliveries?community_id=demo',headers=admin).json()[0]
            assert [p['kind'] for p in job['parts']]==['cover_photo_with_caption','additional_photo','listing_code','sold_notice']
            assert all(p['status']=='sent' and p['transport_mode']=='mock' for p in job['parts'])
            return {'mode':'SIMULATED — NO REAL ZALO OR MODEL','moderator':'synthetic stub, not image understanding',
                'parts':[p['kind'] for p in job['parts']],'receipts':[p['sent_message_id'] for p in job['parts']],
                'duplicate_send':False,'sold_removed_from_search':True,'parent_status':job['status']}


if __name__=='__main__': print(json.dumps(run_demo(),ensure_ascii=False,indent=2))
