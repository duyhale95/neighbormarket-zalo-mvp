"""Local-only UI QA launcher. Uses fake fixture data and test credentials only.

Run with the repository venv. This never reads private/local-config.json or
production credentials. Stop with Ctrl+C. Do not deploy this QA launcher.
"""
import os
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
    env = {**os.environ, 'QA_BACKEND_PORT':'8123', 'BACKEND_URL':'http://127.0.0.1:8123',
           'ADMIN_API_KEY':ADMIN, 'BQL_DEMO_PASSWORD':PASSWORD,
           'BQL_SESSION_SECRET':secrets.token_hex(32), 'APP_ORIGIN':'http://127.0.0.1:3000',
           'BQL_COMMUNITY_ID':'demo', 'NEXT_TELEMETRY_DISABLED':'1'}
    processes = []
    root = ROOT / 'work'
    root.mkdir(exist_ok=True)
    with (root/'frontend-preview.log').open('w',encoding='utf8') as log:
        try:
            processes.append(subprocess.Popen([sys.executable,str(FRONTEND/'tests/backend_fixture.py')],cwd=ROOT,env=env,stdout=log,stderr=log))
            ready('http://127.0.0.1:8123/health',processes[-1])
            processes.append(subprocess.Popen([shutil.which('node'),str(FRONTEND/'node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port','3000'],cwd=FRONTEND,env=env,stdout=log,stderr=log))
            ready('http://127.0.0.1:3000/',processes[-1])
            print('UI QA preview: http://127.0.0.1:3000 (fake fixture data only)',flush=True)
            processes[-1].wait()
        except KeyboardInterrupt:
            pass
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill();process.wait(timeout=10)
