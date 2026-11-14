"""Read-only localhost health checks. Does not claim a connected Zalo listener."""
import argparse
import json
import urllib.error
import urllib.request


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true',help='Run five-scene isolated simulation instead')
    args=parser.parse_args()
    if args.offline:
        from tools.offline_demo import run_demo
        print(json.dumps(run_demo(),ensure_ascii=False,indent=2))
        return
    for name,port in [('FastAPI',8000),('Intake adapter',8001)]:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=3) as response:
                data=json.load(response)
                print(f'{name}: HTTP {response.status}, status={data.get("status", "unverified")}')
        except (OSError,ValueError,urllib.error.URLError):
            print(f'{name}: unavailable; start its local process')
    print('Zalo listener/PM reply/group send: UNVERIFIED. HTTP health is not Zalo connection evidence.')
    print('Next: inspect enabled workflow + Meo Meo account binding, then use MENTOR_LIVE_DEMO.md live checklist.')


if __name__=='__main__': main()
