"""Generate a private image-intake workflow using the existing trusted bridge."""
import argparse
import json
from pathlib import Path
from build_local_workflow import build

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sender-id',required=True);args=parser.parse_args()
    if not args.sender_id.isascii() or not args.sender_id.isdigit():parser.error('sender-id must be ASCII digits')
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'private/local-config.json').read_text(encoding='utf-8-sig'))
    workflow=build(config['bridge_key'],args.sender_id)
    workflow['name']='Meo Meo - Image Safety Intake TEST'
    workflow['description']='Private photo safety intake. Select Meo Meo. Text draft first, photo before confirmation. Uses first image only. Contains local secret.'
    workflow['nodes'][0]['config']['messageTypes']=['image']
    cfg=workflow['nodes'][1]['config']
    cfg.update(url='http://127.0.0.1:8000/bridge/zalo-image',timeout=30000,body='NM-IMAGE:\n{{ $trigger.images.0 }}')
    (root/'private/image-safety-workflow.json').write_text(json.dumps(workflow,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Created private/image-safety-workflow.json. No photo or key transmitted.')
