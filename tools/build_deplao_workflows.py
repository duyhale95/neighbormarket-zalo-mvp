"""Generate private Deplao workflows, never log credentials or enable/send them.

Adapted from source B generators; verified Deplao source SHA in integration plan.
Export importer remaps IDs: template references use unique node labels.
"""
import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

SCHEMA_FIELDS = {
    'trigger.message': {'threadType','fromId','senderRole','ignoreOwn','onlyOwn','keyword','messageTypes','debounceSeconds'},
    'trigger.schedule': {'cronExpression','timezone'},
    'output.httpRequest': {'method','url','headers','body','timeout'},
    'logic.if': {'left','operator','right'},
    'zalo.sendMessage': {'threadId','threadType','message','continueOnError','sendDelayMinSeconds','sendDelayMaxSeconds'},
}
TRIGGER_FIELDS = {'fromId','threadId','threadType','msgId','zaloId','isSelf','content','timestamp'}


def _digits(value: str) -> str:
    if not re.fullmatch(r'[0-9]{1,100}', value):
        raise ValueError('Use verified numeric account/sender/group metadata IDs')
    return value


def _key(value: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,200}', value):
        raise ValueError('Use an ASCII random key of 16–200 characters')
    return value


def _node(label: str, kind: str, config: dict[str, Any], index: int) -> dict:
    return {'id':label,'type':kind,'label':label,'position':{'x':320,'y':40+index*160},'config':config}


def _if(label: str, left: str, operator: str, right: str, index: int) -> dict:
    return _node(label,'logic.if',{'left':left,'operator':operator,'right':right},index)


def _http(label: str, url: str, headers: dict, index: int, body: str = '') -> dict:
    return _node(label,'output.httpRequest',{'method':'POST','url':url,
        'headers':json.dumps(headers),'body':body,'timeout':15000},index)


def _graph(name: str, nodes: list[dict], links: list[tuple[str,str,str]]) -> dict:
    graph={'_deplaoWorkflow':True,'_version':1,'channel':'zalo','name':name,
        'description':'Private local configuration. Bind ONLY Meo Meo; disable old intake consumers. Imported disabled. Never upload logs/exports.',
        'nodes':nodes,'edges':[{'id':f'e{i}','source':a,'sourceHandle':handle,'target':b}
                              for i,(a,b,handle) in enumerate(links)]}
    validate_graph(graph)
    return graph


def build_intake(key: str, account_id: str, sender_id: str) -> dict:
    _key(key); _digits(account_id); _digits(sender_id)
    nodes=[
        _node('ReceivePrivate','trigger.message',{'threadType':'0','fromId':sender_id,
            'senderRole':'all','ignoreOwn':True,'onlyOwn':False,'keyword':'',
            'messageTypes':['text'],'debounceSeconds':0},0),
        _if('AccountOK','{{ $trigger.zaloId }}','equals',account_id,1),
        _http('Intake','http://127.0.0.1:8001/intake',{
            'X-Intake-Key':key,'Content-Type':'text/plain; charset=utf-8',
            'X-Zalo-Account':'{{ $trigger.zaloId }}','X-Zalo-Sender':'{{ $trigger.fromId }}',
            'X-Zalo-Thread':'{{ $trigger.threadId }}','X-Zalo-Message':'{{ $trigger.msgId }}',
            'X-Zalo-Thread-Type':'{{ $trigger.threadType }}','X-Zalo-Self':'{{ $trigger.isSelf }}'},2,
            'NM-TEXT:\n{{ $trigger.content }}'),
        _if('HttpOK','{{ $node.Intake.status }}','equals','200',3),
        _if('HasReply','{{ $node.Intake.data.reply }}','not_empty','',4),
        _node('PrivateReply','zalo.sendMessage',{'threadId':'{{ $trigger.threadId }}','threadType':'0',
            'message':'{{ $node.Intake.data.reply }}','continueOnError':False,
            'sendDelayMinSeconds':1,'sendDelayMaxSeconds':2},5)]
    return _graph('NeighborMarket - Private Intake',nodes,[
        ('ReceivePrivate','AccountOK','default'),('AccountOK','Intake','true'),
        ('Intake','HttpOK','default'),('HttpOK','HasReply','true'),('HasReply','PrivateReply','true')])


def build_publisher(key: str, account_id: str, group_id: str, *, policy_validated: bool = False) -> dict:
    _key(key); _digits(account_id); _digits(group_id)
    if not policy_validated:
        raise ValueError('Validate human policy and allowed group/account before generating a live publisher')
    headers={'X-API-Key':key,'Content-Type':'application/json'}
    job='{{ $node.Claim.data.delivery_id }}'
    token='{{ $node.Claim.data.claim_token }}'
    failbody=json.dumps({'claim_token':token,'outcome':'unknown','error':'other'})
    nodes=[
        _node('Schedule','trigger.schedule',{'cronExpression':'*/20 * * * * *','timezone':'Asia/Ho_Chi_Minh'},0),
        _if('AccountOK','{{ $pageId }}','equals',account_id,1),
        _http('Claim','http://127.0.0.1:8000/deliveries/claim',headers,2),
        _if('ClaimOK','{{ $node.Claim.status }}','equals','200',3),
        _if('AllowedGroup','{{ $node.Claim.data.group_id }}','equals',group_id,4),
        _if('ValidJob','{{ $node.Claim.data.delivery_id }}','regex','^[a-f0-9]{32}$',5),
        _if('ValidToken',token,'regex','^[A-Za-z0-9_-]{20,100}$',6),
        _node('SendGroup','zalo.sendMessage',{'threadId':group_id,'threadType':'1',
            'message':'{{ $node.Claim.data.message }}','continueOnError':False,
            'sendDelayMinSeconds':1,'sendDelayMaxSeconds':2},7),
        _if('RealSend','{{ $node.SendGroup.simulated }}','not_equals','true',8),
        _if('Receipt','{{ $node.SendGroup.msgId }}','regex','^[0-9]{1,100}$',9),
        _http('Ack',f'http://127.0.0.1:8000/deliveries/{job}/sent',headers,10,
            json.dumps({'claim_token':token,'sent_message_id':'{{ $node.SendGroup.msgId }}','transport_mode':'deplao'})),
        _http('Unknown',f'http://127.0.0.1:8000/deliveries/{job}/failure',headers,11,failbody),
    ]
    # Separate branches must never converge: Deplao propagates skips downstream.
    return _graph('NeighborMarket - Approved Publisher',nodes,[
        ('Schedule','AccountOK','default'),('AccountOK','Claim','true'),('Claim','ClaimOK','default'),
        ('ClaimOK','AllowedGroup','true'),('AllowedGroup','ValidJob','true'),
        ('ValidJob','ValidToken','true'),('ValidToken','SendGroup','true'),
        ('SendGroup','RealSend','default'),('RealSend','Receipt','true'),
        ('Receipt','Ack','true'),('Receipt','Unknown','false')])


def validate_graph(graph: dict) -> None:
    """Validate the deliberately small verified schema subset, not every Deplao node."""
    if graph.get('_deplaoWorkflow') is not True or graph.get('_version') != 1 or graph.get('channel') != 'zalo':
        raise ValueError('Unsupported export envelope')
    nodes=graph['nodes']; ids={n['id'] for n in nodes}; labels={n['label'] for n in nodes}
    if len(ids)!=len(nodes) or len(labels)!=len(nodes):
        raise ValueError('Duplicate node identity/label')
    types={n['id']:n['type'] for n in nodes}
    for node in nodes:
        if node['type'] not in SCHEMA_FIELDS or set(node['config'])-SCHEMA_FIELDS[node['type']]:
            raise ValueError('Unverified node or config field')
        for value in node['config'].values():
            if not isinstance(value,str): continue
            for label in re.findall(r'\$node\.([A-Za-z0-9_]+)\.',value):
                if label not in labels: raise ValueError('Unknown node template reference')
            for field in re.findall(r'\$trigger\.([A-Za-z0-9_]+)',value):
                if field not in TRIGGER_FIELDS: raise ValueError('Unknown trigger template field')
    inbound={key:0 for key in ids}
    adjacency={key:[] for key in ids}
    for edge in graph['edges']:
        if edge['source'] not in ids or edge['target'] not in ids:
            raise ValueError('Dangling edge')
        handles={'true','false'} if types[edge['source']]=='logic.if' else {'default'}
        if edge.get('sourceHandle') not in handles: raise ValueError('Unverified edge handle')
        inbound[edge['target']]+=1
        adjacency[edge['source']].append(edge['target'])
    queue=[key for key,count in inbound.items() if count==0]
    if len(queue)!=1 or not types[queue[0]].startswith('trigger.'):
        raise ValueError('Graph must have one trigger root')
    visited=[]
    while queue:
        key=queue.pop(); visited.append(key)
        for target in adjacency[key]:
            inbound[target]-=1
            if inbound[target]==0: queue.append(target)
    if len(visited)!=len(ids): raise ValueError('Cyclic graph')


def write_private(root: Path, output: Path, data: dict) -> None:
    private=(root/'private').resolve()
    target=output.resolve()
    if not target.is_relative_to(private):
        raise ValueError('Credential-bearing output must stay under private/')
    target.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation: do not overwrite a local workflow edited by an operator.
    with target.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2)
    if os.name!='nt': target.chmod(0o600)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account-id',required=True)
    parser.add_argument('--sender-id',required=True,help='One verified tester; do not enable all-resident intake yet')
    parser.add_argument('--group-id',required=True)
    parser.add_argument('--policy-validated',action='store_true',help='Operator verified mandatory review policy and allowed group/account')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'private/local-config.json').read_text(encoding='utf-8-sig'))
    if not config.get('intake_key'):
        parser.error('Run .\\run-intake.ps1 once to initialize a distinct intake key, then stop it before generation')
    intake=build_intake(config['intake_key'],args.account_id,args.sender_id)
    publisher=build_publisher(config['bridge_key'],args.account_id,args.group_id,policy_validated=args.policy_validated)
    outputs={'deplao-intake.json':intake,'deplao-publisher.json':publisher,
        'zalo-channel.json':{'account_id':args.account_id,'sender_ids':[args.sender_id],
            'group_id':args.group_id,'community_id':'demo','policy_validated':True}}
    if any((root/'private'/name).exists() for name in outputs):
        parser.error('Existing generated files found. Preserve/review them before generating new files; nothing overwritten')
    for name,data in outputs.items(): write_private(root,root/'private'/name,data)
    print('Created private Deplao intake/publisher/channel files. No login, workflow activation or message send performed.')


if __name__=='__main__': main()
