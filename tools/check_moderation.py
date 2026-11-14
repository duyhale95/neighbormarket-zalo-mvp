"""Optional synthetic live check after the user stores a NEW local key."""
import io
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from backend.images import OpenAIModerator

env=os.environ.copy();env['NEIGHBOR_MOD_KEY']=str(Path('private/moderation-key.xml').resolve())
script="$s=Import-Clixml -LiteralPath $env:NEIGHBOR_MOD_KEY; $p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); try {[Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($p))} finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}"
result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,text=True,timeout=15)
if result.returncode or not result.stdout.strip():raise SystemExit('No readable local moderation key. Run setup-moderation.ps1 first.')
out=io.BytesIO();Image.new('RGB',(32,32),'blue').save(out,format='PNG')
answer=OpenAIModerator(result.stdout.strip()).check(out.getvalue(),'image/png','Synthetic blue square for safety API test')
print('MODERATION_TEST_STATUS='+answer['status']+'; synthetic image only; key not printed')
if answer['status']!='clear':raise SystemExit(1)
