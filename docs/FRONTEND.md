# Golden Sunrise frontend and BQL demo

This is an independent concept, not an official Vinhomes, Zalo or VinAI product.
The backend's real-Zalo connector remains unverified. This frontend does not
log in to Deplao or Zalo, send group messages, claim deliveries or retry sends.

## Windows setup

Requirements: Python 3.11+, Windows PowerShell 5.1 or PowerShell 7, Node.js 22.13+ (tested with 24.21.0), npm.

Terminal 1, at `C:\Users\Admin\neighbormarket-zalo-mvp`:

```powershell
if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:ZALO_COMMUNITY_ID = 'demo'
$env:ZALO_LEGIT_GROUP_ID = 'mock-legit-group' # fake label; use permitted ID for a future live test
.\run-local.ps1
```

Configure the group before approval. Existing backend compatibility allows an
approval with `delivery_status: not_configured`; that creates no job and is not
backfilled. The UI displays that warning after the real backend response.

Terminal 2:

```powershell
Set-Location C:\Users\Admin\neighbormarket-zalo-mvp\frontend
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
notepad .env.local
```

Set all server-only values in `frontend/.env.local`:

| Variable | Value |
| --- | --- |
| `BACKEND_URL` | `http://127.0.0.1:8000` for local FastAPI |
| `ADMIN_API_KEY` | The `admin_key` in ignored `private/local-config.json`; keep private |
| `BQL_DEMO_PASSWORD` | A demo password, 12–256 characters |
| `BQL_SESSION_SECRET` | At least 32 random characters, separate from API key/password |
| `APP_ORIGIN` | Exact browser origin, e.g. `http://127.0.0.1:3000` |
| `BQL_COMMUNITY_ID` | `demo`, or the intended community |

Do not prefix credentials with `NEXT_PUBLIC_`. `.env.local` is ignored by Git.
Use the exact configured origin (`localhost` and `127.0.0.1` are distinct).

```powershell
npm run dev
```

For the production server: `npm run build` then `npm run start`. Open
`http://127.0.0.1:3000` and `/bql/login`. Use the configured BQL demo password;
never enter the backend API key into the browser. Missing settings lock the
dashboard and show setup instructions. Restart after environment changes.

### Existing checkout and Windows startup errors

- If `neighbormarket-demo` already exists, reuse it; do not clone over or delete
  it. Check `git status --short --branch`. With a clean working tree on this
  feature branch, use `git pull --ff-only origin feat/vinhomes-sunrise-landing-bql-ui`.
  Preserve local changes before switching branches or updating.
- If `.venv\Scripts\python.exe` already runs, skip `python -m venv .venv`.
  Recreating an active environment can fail because its Python executable is in
  use. Calling its Python directly does not require activation.
- If `pwsh` is not recognized, run `.\run-local.ps1` in the existing Windows
  PowerShell window. The launcher supports Windows PowerShell 5.1 and PowerShell
  7, and preserves existing `private/local-config.json` and database files.
- If script execution is blocked, set
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` in that
  window, then run `.\run-local.ps1` again.
- Windows PowerShell 5.1 does not provide static
  `RandomNumberGenerator.GetBytes(length)` or `Convert.ToHexString`. Generate
  new demo credentials with the existing Python interpreter instead:

  ```powershell
  $password = & ..\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(16))"
  $secret = & ..\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
  ```

  Run these from `frontend/`. Only save new credentials to `.env.local` after
  both commands succeed. Preserve existing nonempty credentials. If an earlier
  attempt saved empty values, fill `BQL_DEMO_PASSWORD` and `BQL_SESSION_SECRET`
  and restart Next.js. Keep the file and generated values private.

## Routes and integration

| Route | Function |
| --- | --- |
| `/` | Public Golden Sunrise landing page, all product previews labelled illustrative |
| `/bql/login` | Server-configured demo password gate |
| `/bql` | Real `/stats`, listing queue and delivery summary |
| `/bql/listings` | Filter, inspect and approve/reject with reason and confirmation |
| `/bql/deliveries` | Read delivery states; explicitly reconcile `unknown` |
| `/api/bql/*` | Authenticated, allowlisted server BFF; no arbitrary proxy |

The BFF sets `X-API-Key` on server-to-FastAPI requests, validates response schemas
and strips unknown fields. Community comes from server configuration, not the
browser. Reconciliation verifies the delivery belongs to that community before
calling the existing API. Backend 401/404/409/422 responses become safe UI errors.
An ambiguous mutation timeout instructs the operator to refresh and inspect
state, not blindly repeat the action.

The session is HMAC-signed, expires after eight hours, and uses an HttpOnly,
SameSite=Strict cookie. HTTPS `APP_ORIGIN` enables Secure cookies. Login, logout,
review and reconciliation check Origin; mutations require JSON. Admin data is
not cached. Backend credentials, PM text and session tokens are not logged by
the frontend. Rotate `BQL_SESSION_SECRET` to revoke issued sessions; logout
removes the local browser cookie. The process-local login throttle is for demo
use; this does not replace individual accounts or a shared production limiter.

## Assets and typography

Both PNGs were supplied by the user during implementation. Originals are in
`assets/`; public copies are in `frontend/public/brand/`. The logo is RGBA
1200×633 and the symbol is RGBA 1200×1200. Files are copied without modification;
rendering preserves their aspect ratios, colors and transparency. No external
logo was downloaded. Replace only with an authorized original file, keeping the
same names, then rebuild. Local Fontsource packages supply Outfit and Be Vietnam
Pro; builds do not depend on a Google Fonts request.

## Verification

At repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

In `frontend/`:

```powershell
npm test
npm run typecheck
npm run lint
npm run build
npm audit
```

After the build, run real HTTP tests at repository root:

```powershell
.\.venv\Scripts\python.exe frontend/tests/http_integration.py
```

This launches isolated FastAPI/Next.js servers on ports 8124, 3110, 3111 and 3112,
using disposable fake data. It checks authentication, CSRF, real mutations,
backend errors, offline behavior and absence of the QA admin sentinel from
client JS/HTML. It stops its processes and cleans up the disposable database.
No outbound Zalo calls are made.

Optional browser QA with fake records (ports 8123 and 3000 must be free):

```powershell
.\.venv\Scripts\python.exe frontend/tests/preview.py
```

This test-only launcher never reads the real private config. Its password is
the explicitly fake `PASSWORD` constant in `frontend/tests/http_integration.py`.
Stop with Ctrl+C. Do not deploy the fixture launcher or present fixture records
as resident data.

`minimatch` under the TypeScript ESLint parser is overridden to patched 11.0.8
for advisory GHSA-g3hv-75wg-m249. Lint/build checks exercise the override.

## Demo walkthrough and limits

Verification recorded on 14 November 2026, Windows, Node 24.21.0:

- Base: `4c181621ba2ae3ca19e60af2503542ec3d758299`, clean working tree before changes.
- Existing backend: baseline and final **37/37 pass** (one existing Starlette deprecation warning).
- Frontend security unit tests: **4/4 pass**. Production HTTP integration: **24/24 checks pass**.
- TypeScript, ESLint, formatting check and production build pass; npm audit reports no vulnerabilities.
- Browser QA at 360×800, 768×1024 and 1440×900: no horizontal page overflow; tables/phone previews scroll within their own containers.
- Browser exercised login, approval confirmation, rejection, disabled approval for sensitive content, and unknown delivery reconciliation against the isolated fixture backend.
- Mobile menu, Enter-key FAQ interaction, proportional logo rendering and browser console were checked. No console errors/warnings were observed.
- Screenshot records contain fake QA data, not resident activity. Reduced motion is supported in CSS; no OS-level reduced-motion toggle was exercised.

1. On `/`, explore the scenarios, phone flow, labelled dashboard preview and FAQ.
2. Log in at `/bql/login`; verify connection state and live backend metrics.
3. Create a draft and confirm it through the existing `/events` flow (see DEMO.md).
4. In `/bql/listings`, inspect seller, condition and moderation flags. Enter a
   reason, choose approve/reject, and confirm the actual backend mutation.
5. In `/bql/deliveries`, inspect the resulting queue entry. A stored `sent`
   acknowledgement may be mock; it does not prove a real Zalo send.
6. For `unknown`, stop/check the old publisher and verify the group before
   recording the decision and evidence. There is no automatic retry control.

Community Monitoring, Resident Risk Alerts and MLOps are visibly marked
“Đang phát triển”; no incidents, risk scores or model evaluations are invented.
The backend returns at most 100 recent listings/deliveries; UI filters operate
within those returned records. Refresh is explicit, not realtime streaming.
There are no personal BQL accounts, resident verification, price-range search,
image upload or newly implemented Zalo connector. Backend business contracts
and marketplace code are unchanged by this frontend branch.
