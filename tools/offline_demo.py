"""Five-scene mentor simulation. Disposable target DB; no network/paid AI/Zalo."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.channels import MockZaloTransport
from backend.intake_bridge import create_intake_app
from backend.publisher import Publisher


def run_demo() -> dict:
    with tempfile.TemporaryDirectory(prefix='nm-offline-') as directory, patch.dict('os.environ',{'AI_ENABLED':'false'}):
        backend=TestClient(create_app(Path(directory)/'market.db','offline-bridge','offline-admin',target_group_id='mock-legit-group'))
        adapter=TestClient(create_intake_app('http://backend','offline-bridge','offline-intake','demo',
            client=backend,account_id='303',allowed_sender_ids={'202','404'}))
        transport=MockZaloTransport('303','mock-legit-group')
        sequence=0
        admin={'X-API-Key':'offline-admin'}

        def pm(text: str, sender: str = '202', message_id: str | None = None) -> dict:
            nonlocal sequence
            sequence+=1
            response=adapter.post('/intake',headers={'X-Intake-Key':'offline-intake',
                'Content-Type':'text/plain; charset=utf-8','X-Zalo-Account':'303',
                'X-Zalo-Sender':sender,'X-Zalo-Thread':sender,'X-Zalo-Message':message_id or str(sequence),
                'X-Zalo-Self':'false','X-Zalo-Thread-Type':'0'},content='NM-TEXT:\n'+text)
            response.raise_for_status()
            body=response.json()
            assert body['thread_id']==sender
            if body['reply']: transport.send_private(sender,body['reply'])
            return body

        try:
            text='Mình muốn bán chiếc ghế công thái học, giá 800k, dùng được 6 tháng.'
            draft=pm(text,message_id='1001')
            replay=pm(text,message_id='1001')
            assert replay==draft
            rows=backend.get('/listings?community_id=demo',headers=admin).json()
            assert len(rows)==1 and rows[0]['status']=='draft'
            listing_id=rows[0]['id']
            assert rows[0]['price_vnd']==800000
            pm('xác nhận')
            pending=backend.get('/listings?community_id=demo',headers=admin).json()[0]
            assert pending['status']=='pending' and pending['moderation']['requires_review']
            assert Publisher(backend,'offline-bridge',transport,'mock-legit-group').process_once().status=='idle'
            approval=backend.post(f'/listings/{listing_id}/review',headers=admin,
                json={'community_id':'demo','action':'approve','reason':'Đã kiểm tra dữ liệu demo tổng hợp'})
            assert approval.json()['delivery_status']=='queued'
            worker=Publisher(backend,'offline-bridge',transport,'mock-legit-group')
            sent=worker.process_once()
            assert sent.status=='sent' and sent.simulated and worker.process_once().status=='idle'
            buyer=pm('tìm ghế',sender='404')
            assert listing_id in buyer['reply'] and '202' not in buyer['reply']
            pm('Mình muốn bán chiếc máy giặt, giá 800k, dùng 6 tháng, đặt cọc trước.')
            pm('ok')
            risk=backend.get('/listings?community_id=demo',headers=admin).json()[0]
            assert risk['status']=='pending' and 'suspicious' in risk['moderation']['categories']
            assert worker.process_once().status=='idle'
            jobs=backend.get('/deliveries?community_id=demo',headers=admin).json()
            assert len(jobs)==1 and jobs[0]['transport_mode']=='mock'
            return {'mode':'SIMULATED — NO REAL ZALO', 'scenes':[
                {'scene':'seller','result':'structured draft; duplicate event creates one listing'},
                {'scene':'moderation','result':'seller confirmed; mandatory BQL pending'},
                {'scene':'publisher','result':'authorized approval; one group send; mock receipt recorded'},
                {'scene':'buyer','result':'approved listing found through private intake'},
                {'scene':'safety','result':'suspicious listing flagged; remains pending, no publication'}],
                'delivery_status':jobs[0]['status'],'transport_mode':jobs[0]['transport_mode'],
                'group_messages':sum(item['kind']=='group' for item in transport.sent)}
        finally:
            adapter.close(); backend.close()


if __name__=='__main__':
    print(json.dumps(run_demo(),ensure_ascii=False,indent=2))
