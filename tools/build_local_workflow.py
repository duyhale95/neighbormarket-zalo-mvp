"""Build an importable workflow with a local key. Output must stay private."""
import argparse
import json
from pathlib import Path


def build(key, sender_id):
    nodes = [
        {'id':'receive','type':'trigger.message','label':'ReceivePrivate', 'position':{'x':320,'y':40},
         'config':{'threadType':'0','fromId':sender_id,'senderRole':'all','ignoreOwn':True,
                   'onlyOwn':False,'keyword':'','messageTypes':['text'],'debounceSeconds':0}},
        {'id':'backend','type':'output.httpRequest','label':'MarketBackend','position':{'x':320,'y':230},
         'config':{'method':'POST','url':'http://127.0.0.1:8000/bridge/zalo','timeout':15000,
                   'headers':json.dumps({'X-API-Key':key,'X-Sender-Id':'{{ $trigger.fromId }}',
                                         'X-Event-Id':'{{ $trigger.msgId }}','Content-Type':'text/plain; charset=utf-8'}),
                   'body':'NM-TEXT:\n{{ $trigger.content }}'}},
        {'id':'ok','type':'logic.if','label':'BackendOK','position':{'x':320,'y':430},
         'config':{'left':'{{ $node.MarketBackend.status }}','operator':'equals','right':'200'}},
        {'id':'send','type':'zalo.sendMessage','label':'ReplyToSender','position':{'x':320,'y':630},
         'config':{'threadId':'{{ $trigger.threadId }}','threadType':'0',
                   'message':'{{ $node.MarketBackend.data.reply }}','sendDelayMinSeconds':1,'sendDelayMaxSeconds':2}},
    ]
    return {'_deplaoWorkflow':True,'_version':1,'channel':'zalo',
            'name':'Meo Meo - Local Market Backend TEST',
            'description':'Local text test. Select Meo Meo account. Disable old auto-reply workflow before enabling. Contains local secret; never export publicly.',
            'nodes':nodes,'edges':[
                {'id':'e1','source':'receive','sourceHandle':'default','target':'backend'},
                {'id':'e2','source':'backend','sourceHandle':'default','target':'ok'},
                {'id':'e3','source':'ok','sourceHandle':'true','target':'send'}]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sender-id', required=True, help='Confirmed tester Zalo ID; no all-user auto-reply in this test')
    args = parser.parse_args()
    if not args.sender_id.isascii() or not args.sender_id.isdigit():
        parser.error('sender-id must contain ASCII digits')
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root/'private/local-config.json').read_text(encoding='utf-8-sig'))
    target = root/'private/deplao-local-workflow.json'
    target.write_text(json.dumps(build(config['bridge_key'],args.sender_id),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Created private/deplao-local-workflow.json (contains local key; do not share)')
