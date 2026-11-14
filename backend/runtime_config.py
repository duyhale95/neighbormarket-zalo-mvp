"""Live image transport needs the same private operator attestations as the graphs."""
import json
import os
from pathlib import Path
from tools.deplao_compat import STRICT_ENGINE_SHA256


def images_enabled() -> bool:
    if os.getenv('ZALO_IMAGES_ENABLED','false').lower()!='true': return False
    path=Path(os.getenv('ZALO_CHANNEL_CONFIG','private/zalo-channel.json'))
    config=json.loads(path.read_text(encoding='utf-8-sig'))
    if (any(config.get(key) is not True for key in ('strict_account_binding_verified','policy_validated','image_metadata_verified','images_enabled'))
            or config.get('deplao_engine_sha256')!=STRICT_ENGINE_SHA256):
        raise ValueError('Live images blocked: verify strict installed build and photo metadata before generation')
    for variable,key in (('ZALO_ACCOUNT_ID','account_id'),('ZALO_COMMUNITY_ID','community_id'),('COMMUNITY_ID','community_id'),('ZALO_LEGIT_GROUP_ID','group_id')):
        value=os.getenv(variable)
        if value and value!=config.get(key): raise ValueError('Runtime channel does not match validated private manifest')
    return True
