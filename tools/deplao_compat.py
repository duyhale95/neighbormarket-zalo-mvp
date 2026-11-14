"""Fail-closed source compatibility gate; no login, runtime modification or send.

The reviewed upstream workflow engine can borrow another account connection.
Only the exact reviewed engine with the supplied strict-binding patch is accepted.
This checks source bytes, NOT whether that build is actually installed/running.
"""
import argparse
import hashlib
from pathlib import Path

REVIEWED_UPSTREAM_SHA256='32cbe2568939e8aa57e004f22e5578d4c0a6630c74d5c93bafb35536184ebb07'
STRICT_ENGINE_SHA256='e46f192bc6da62a2741d501c864f6d0f7f35168ea2e6bf9c8f895f25e4297705'


def verify_strict_runtime(source_root: Path) -> str:
    engine=source_root/'src/services/workflow/WorkflowEngineService.ts'
    text=engine.read_text(encoding='utf-8-sig')
    digest=hashlib.sha256(text.encode()).hexdigest()
    if digest!=STRICT_ENGINE_SHA256:
        raise ValueError('Live generation blocked: engine strict account binding is not verified. '
                         'See docs/DEPLAO_COMPATIBILITY.md; never enable the old graphs on this build.')
    return digest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    try:
        verify_strict_runtime(args.source)
    except (OSError,ValueError) as error:
        parser.exit(1, str(error)+'\n')
    print('Source compatibility passed. Installed build, account, listener and Zalo delivery remain unverified.')
