"""Local-only UI QA launcher. Uses fake fixture data and test credentials only.

Run with the repository venv. This never reads private/local-config.json or
production credentials. Stop with Ctrl+C. Do not deploy this QA launcher.
"""
import os
import argparse
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from backend_fixture import ADMIN
from http_integration import PASSWORD, ready

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / 'frontend'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=3000)
    parser.add_argument('--backend-port',type=int,default=8123)
    args = parser.parse_args()
    origin = f'http://127.0.0.1:{args.port}'
    backend_url = f'http://127.0.0.1:{args.backend_port}'
    env = {**os.environ, 'QA_BACKEND_PORT':str(args.backend_port), 'BACKEND_URL':backend_url,
           'ADMIN_API_KEY':ADMIN, 'BQL_DEMO_PASSWORD':PASSWORD,
           'BQL_SESSION_SECRET':secrets.token_hex(32), 'APP_ORIGIN':origin,
           'BQL_COMMUNITY_ID':'demo', 'NEXT_TELEMETRY_DISABLED':'1'}
    processes = []
    root = ROOT / 'work'
    root.mkdir(exist_ok=True)
    with (root/'frontend-preview.log').open('w',encoding='utf8') as log:
        try:
            processes.append(subprocess.Popen([sys.executable,str(FRONTEND/'tests/backend_fixture.py')],cwd=ROOT,env=env,stdout=log,stderr=log))
            ready(backend_url+'/health',processes[-1])
            processes.append(subprocess.Popen([shutil.which('node'),str(FRONTEND/'node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',str(args.port)],cwd=FRONTEND,env=env,stdout=log,stderr=log))
            ready(origin+'/',processes[-1])
            print(f'UI QA preview: {origin} (fake fixture data only)',flush=True)
            processes[-1].wait()
        except KeyboardInterrupt:
            pass
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill();process.wait(timeout=10)
