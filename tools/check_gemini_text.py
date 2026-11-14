"""Synthetic API smoke. Never prints the API key or server error payload."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.ai_text import GeminiTextExtractor, AIUnavailable
from backend.app import create_app


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--key-file',required=True)
    parser.add_argument('--model',required=True)
    args=parser.parse_args()
    env=os.environ.copy();env['NEIGHBOR_KEY_PATH']=str(Path(args.key_file).resolve())
    script="$s=Import-Clixml -LiteralPath $env:NEIGHBOR_KEY_PATH; $p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); try {[Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($p))} finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                          env=env,capture_output=True,text=True,timeout=15)
    if result.returncode or not result.stdout.strip():
        raise SystemExit('Cannot read local DPAPI key. No secret was printed.')
    ai=GeminiTextExtractor(result.stdout.strip(),args.model)
    start=time.monotonic()
    with tempfile.TemporaryDirectory() as folder, TestClient(create_app(Path(folder)/'smoke.db','smoke-bridge','smoke-admin',extractor=ai)) as client:
        def send(text,id):
            r=client.post('/events',headers={'X-API-Key':'smoke-bridge'},json=dict(event_id=id,sender_id='synthetic',community_id='synthetic',text=text))
            r.raise_for_status();return r.json()
        first=send('Mình muốn thanh lý ghế làm việc 500k.','one')
        assert first['status']=='incomplete' and first['missing_fields']==['condition']
        second=send('Ghế đã dùng 6 tháng, không hư hỏng.','two')
        assert second['status']=='draft' and second['listing_id']==first['listing_id']
        rows=client.get('/listings?community_id=synthetic',headers={'X-API-Key':'smoke-admin'}).json()
        assert len(rows)==1 and rows[0]['price_vnd']==500000 and rows[0]['status']=='draft'
    print(f'GEMINI_TEXT_SMOKE_OK: 2 synthetic backend turns, {time.monotonic()-start:.1f}s total; temp DB removed, no Zalo sent')


if __name__=='__main__':
    try:main()
    except AIUnavailable:
        raise SystemExit('Gemini smoke failed; no key or provider error payload printed.')
