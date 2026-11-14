"""Prepare private group target and Deplao polling workflow; never sends Zalo."""
import argparse
import json
import re
from pathlib import Path


def build(key):
    headers=json.dumps({'X-API-Key':key,'Content-Type':'application/json','X-Publisher-Version':'2'})
    nodes=[
        {'id':'schedule','type':'trigger.schedule','label':'Every20Seconds','position':{'x':320,'y':40},
         'config':{'cronExpression':'*/20 * * * * *','timezone':'Asia/Ho_Chi_Minh'}},
        {'id':'claim','type':'output.httpRequest','label':'Claim','position':{'x':320,'y':200},
         'config':{'method':'POST','url':'http://127.0.0.1:8000/group-publications/claim','headers':headers,'timeout':10000}},
        {'id':'httpok','type':'logic.if','label':'ClaimOK','position':{'x':320,'y':360},
         'config':{'left':'{{ $node.Claim.status }}','operator':'equals','right':'200'}},
        {'id':'ready','type':'logic.if','label':'HasJob','position':{'x':320,'y':520},
         'config':{'left':'{{ $node.Claim.data.ready }}','operator':'equals','right':'true'}},
        {'id':'send','type':'zalo.sendMessage','label':'PostToGroup','position':{'x':320,'y':680},
         'config':{'threadId':'{{ $node.Claim.data.group_id }}','threadType':'1',
                   'message':'{{ $node.Claim.data.message }}','continueOnError':False,'sendDelayMinSeconds':1,'sendDelayMaxSeconds':2}},
        {'id':'receipt','type':'logic.if','label':'HasReceipt','position':{'x':320,'y':840},
         'config':{'left':'{{ $node.PostToGroup.msgId }}','operator':'not_empty','right':''}},
        {'id':'ack','type':'output.httpRequest','label':'SaveReceipt','position':{'x':320,'y':1000},
         'config':{'method':'POST','url':'http://127.0.0.1:8000/group-publications/{{ $node.Claim.data.job_id }}/ack',
                   'headers':headers,'timeout':10000,
                   'body':'{"token":"{{ $node.Claim.data.token }}","message_id":"{{ $node.PostToGroup.msgId }}"}'}},
    ]
    nodes.extend([
        {'id':'media','type':'logic.if','label':'HasPhoto','position':{'x':320,'y':660},
         'config':{'left':'{{ $node.Claim.data.has_image }}','operator':'equals','right':'true'}},
        {'id':'photo','type':'zalo.sendImage','label':'PostPhoto','position':{'x':620,'y':840},
         'config':{'threadId':'{{ $node.Claim.data.group_id }}','threadType':'1',
                   'filePath':'{{ $node.Claim.data.image_path }}','message':'{{ $node.Claim.data.message }}','continueOnError':False}},
        {'id':'photoReceipt','type':'logic.if','label':'HasPhotoReceipt','position':{'x':620,'y':1000},
         'config':{'left':'{{ $node.PostPhoto.msgId }}','operator':'not_empty','right':''}},
        {'id':'photoAck','type':'output.httpRequest','label':'SavePhotoReceipt','position':{'x':620,'y':1160},
         'config':{'method':'POST','url':'http://127.0.0.1:8000/group-publications/{{ $node.Claim.data.job_id }}/ack',
                   'headers':headers,'timeout':10000,
                   'body':'{"token":"{{ $node.Claim.data.token }}","message_id":"{{ $node.PostPhoto.msgId }}"}'}},
    ])
    positions={'schedule':(480,40),'claim':(480,220),'httpok':(480,400),'ready':(480,580),'media':(480,760),
               'send':(160,960),'receipt':(160,1140),'ack':(160,1320),
               'photo':(800,960),'photoReceipt':(800,1140),'photoAck':(800,1320)}
    for node in nodes:
        x,y=positions[node['id']];node['position']={'x':x,'y':y}
    # Separate receipt branches prevent IF skip propagation from suppressing a shared ACK.
    edges=[]
    for i,(a,b,handle) in enumerate([('schedule','claim','default'),('claim','httpok','default'),('httpok','ready','true'),
                                    ('ready','media','true'),('media','send','false'),('send','receipt','default'),('receipt','ack','true'),
                                    ('media','photo','true'),('photo','photoReceipt','default'),('photoReceipt','photoAck','true')]):
        edges.append({'id':f'e{i}','source':a,'target':b,'sourceHandle':handle})
    return {'_deplaoWorkflow':True,'_version':1,'channel':'zalo','name':'Meo Meo - Publish Approved with Photos v2',
            'description':'Select Meo Meo; disable previous GROUP publisher, keep private chat and image intake workflows. v2 sends stored product photos with caption, then extra photos and copyable code. Local file paths require same machine. Contains local key: never share.',
            'nodes':nodes,'edges':edges}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--group-id',required=True);parser.add_argument('--group-name',required=True)
    parser.add_argument('--community',default='demo')
    args=parser.parse_args()
    if not re.fullmatch(r'[0-9]{1,100}',args.group_id) or not 1<=len(args.group_name.strip())<=200 or not 1<=len(args.community)<=100:
        parser.error('Invalid target')
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'private/local-config.json').read_text(encoding='utf-8-sig'))
    (root/'private/group-settings.json').write_text(json.dumps({'community_id':args.community,'group_id':args.group_id,'group_name':args.group_name.strip()},ensure_ascii=False),encoding='utf-8')
    (root/'private/group-publisher-workflow-v2.json').write_text(json.dumps(build(config['bridge_key']),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Created private group settings and publisher workflow. No Zalo message sent.')
