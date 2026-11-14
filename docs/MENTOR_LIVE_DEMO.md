# NeighborMarket integrated mentor demo

This branch keeps one FastAPI marketplace, one SQLite database and the existing
Next.js BQL login/BFF. Deplao is the primary personal-account transport. The
partner Bot Platform token cannot log in Meo Meo in Deplao. No Bot Platform
poller or second marketplace service is started.

## Evidence checklist — do not conflate these steps

| Step | Current evidence |
| --- | --- |
| Backend/unit/integration tests | Automated, synthetic records; see plan verification ledger |
| Five-scene offline pipeline | Passed; mock transport and mock message ID |
| Deplao graph fields | Checked against source SHA 2162f077d49f3b990121717fe6596fb3f0941e2f; generator tests |
| Strict account binding | Stock reviewed engine fails this requirement; live generation is blocked |
| Installed Deplao version/schema matches | **Not verified on the installed application** |
| Meo Meo application connected | **Unverified** |
| Real private message received | **Unverified** |
| Real reply reaches original PM | **Unverified** |
| Meo Meo has deputy rights in read-only Legit group | **Unverified** |
| Real group post appears | **Unverified** |
| Real Zalo receipt matches saved message ID | **Unverified** |
| DB status updated after real receipt | **Unverified** |

Only the operator should mark a live row complete, recording local timestamp,
workflow run ID, listing/delivery IDs, and observed group receipt. Keep actual
resident messages, screenshots with identity, workflow exports and credentials
private. The Deplao engine itself logs message snippets and stores rendered HTTP
inputs (including header secrets): protect its local logs and never upload them.

## A. Fully offline fallback — works without a Zalo account or model key

At the feature checkout, e.g. `C:\Users\Admin\neighbormarket-zalo-mvp`:

```powershell
if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.offline_demo
```

After dependencies are installed this needs no network. It creates and removes
a disposable SQLite database, explicitly disables cloud AI, sends nothing to
Zalo, and prints `SIMULATED — NO REAL ZALO`. Expected: five successful scenes,
one group message, `delivery_status=sent`, `transport_mode=mock`.

1. Seller synthetic PM -> authenticated raw `/intake` -> natural structured draft.
2. Same message ID replay -> same backend result, one listing. Seller confirms;
   listing stays pending and cannot be claimed.
3. An authorized BQL API review creates one queued job. Mock publisher claims,
   records one send/receipt; polling again does not send again.
4. Buyer private `tìm ghế` returns the approved listing without seller identity.
5. A payment-before-handover phrase produces an advisory flag; listing stays
   pending and does not create another delivery.

For visual fallback use `frontend/tests/preview.py` as documented in FRONTEND.md;
it is a separate disposable QA data set, clearly synthetic. It never loads the
real private config. Do not present QA counts as resident activity.

## B. Prepare the actual local services (Windows PowerShell 5.1 or 7)

**Live prerequisite:** read DEPLAO_COMPATIBILITY.md first. The stock reviewed
Deplao engine can borrow another account connection. Live workflow generation
and intake startup are intentionally refused until an operator has reviewed,
built and verified the supplied strict-binding patch in a separate Deplao
checkout. This has not been done to the installed application. Use fallback A
while this blocker remains; do not enable old workflow exports.

Do not clone over an existing directory or recreate an active `.venv`. Check
`git status --short --branch` and preserve uncommitted work before updating.
Use the same directory for all services; do not mix keys from the demo checkout
with another checkout. No `pwsh` command is required.

Terminal 1 (backend initialization, text-only/no paid model):

```powershell
Set-Location C:\Users\Admin\neighbormarket-zalo-mvp
$env:AI_ENABLED = 'false'
$env:ZALO_COMMUNITY_ID = 'demo'
$env:ZALO_LEGIT_GROUP_ID = 'mock-legit-group'
.\run-local.ps1
```

This first run creates private/local-config.json if missing. Stop it with Ctrl+C
before replacing the mock target with validated trusted configuration. Existing
data and keys are preserved. Back up a database while its writer is stopped
before applying new code/migrations; no downgrade or database deletion is needed.

Initialize a third distinct key without starting an inbound listener:

```powershell
.\run-intake.ps1 -InitializeOnly
```

Have the group owner verify the chosen group, Meo Meo account, tester identity,
and mandatory human review policy. The owner must manually configure Meo Meo as
deputy and residents as read-only, then verify the actual send permission. This
code never changes group permissions or invites anyone.

Only after those checks, replace numeric placeholders with metadata IDs:

```powershell
.\.venv\Scripts\python.exe -m tools.build_deplao_workflows --account-id ACCOUNT_ID --sender-id TESTER_ID --group-id GROUP_ID --community demo --deplao-source C:\path\to\reviewed-strict-deplao --installed-build-verified --policy-validated
```

This writes `private/deplao-intake.json`, `private/deplao-publisher.json` and
`private/zalo-channel.json`. It refuses existing output files; preserve/review
them before regenerating. The flag is an operator attestation, not an automated
verification of Zalo rights or installed source. Source must match the reviewed
strict engine hash; unmodified/unknown builds fail closed. No workflow is imported/enabled and no message is
sent by the generator. Do not commit or share the generated files.

Restart Terminal 1 with `.\run-local.ps1`; it loads the trusted group/community
from private/zalo-channel.json. Configure before approving new listings: approvals
made without a matching target create no job and are not automatically backfilled.

Terminal 2 (trusted transport adapter, no business database):

```powershell
Set-Location C:\Users\Admin\neighbormarket-zalo-mvp
.\run-intake.ps1
```

It runs port 8001, forwards only to backend 8000, pins account/community/tester
from the private config, and has no standalone listing/review state.

Terminal 3 (Next.js, see FRONTEND.md for full env setup):

```powershell
Set-Location C:\Users\Admin\neighbormarket-zalo-mvp\frontend
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
notepad .env.local
npm run dev
```

Set BACKEND_URL=http://127.0.0.1:8000, the same backend admin_key, a 12+ character
BQL_DEMO_PASSWORD, 32+ character BQL_SESSION_SECRET, APP_ORIGIN=http://127.0.0.1:3000
and BQL_COMMUNITY_ID=demo. Keep all credentials server-side. Existing nonempty
values should be preserved. For random values compatible with PowerShell 5.1,
use Python `secrets.token_hex`, not newer static .NET APIs. Restart Next.js after
editing env. Log in at `/bql/login` with the demo password, never the admin key.

## C. Import Deplao, then diagnose the listener before enabling publication

1. Complete the strict-binding source/build and disconnected-account negative
   test in DEPLAO_COMPATIBILITY.md, then verify the node/output schema. Import
   private/deplao-intake.json (import creates a disabled workflow).
2. Bind exactly Meo Meo in the workflow account selector. Import does not preserve
   account binding; labels are used for templates because node IDs are remapped.
3. Disable the old Gemini auto-reply and every other marketplace inbound consumer
   for this account. Do not run partner Bot Platform polling alongside it.
4. Check trigger: private `threadType=0`, senderRole=all, ignoreOwn=true,
   onlyOwn=false, messageTypes=[text], fromId=tester, debounceSeconds=0.
5. Enable ONLY the intake workflow. Verify Meo Meo is connected; if disconnected,
   reconnect manually using the normal Deplao account UI. Do not export a session.
6. Run the read-only local helper:
   `.\.venv\Scripts\python.exe -m tools.check_listener`.
   Both HTTP services should be healthy; this does not prove Zalo is connected.
7. Send a real tester PM. Inspect the trigger run locally: zaloId, fromId, msgId,
   threadId, threadType=0, isSelf=false must exist. Do not substitute a random ID.
8. Check Intake node reaches `/intake`, HTTP 200 and reply. Metadata travels in
   headers and text/plain body starts with literal `NM-TEXT:` plus newline.
   Quotes, backslashes and `{{...}}` in resident content remain data.
9. Check the reply reaches the same PM. Self messages/group events must not start
   another intake run. Backend business idempotency is guaranteed; private reply
   network exactly-once delivery is not guaranteed if an upstream event repeats.
10. If the trigger never appears, check enabled state/account binding/filters,
    session reconnect and engine event dispatch. Manual Gemini Run/Simulate does
    not verify the event listener. Record this as a blocker and use fallback A.

Only after PM delivery and policy/group checks pass, import the publisher, bind
Meo Meo only, inspect AccountOK/group ID, save and enable it. Do not use a manual
node execution with made-up claim/token/receipt as evidence of live publication.

## D. Five live scenes (remain unchecked until personally observed)

1. **Seller** PM: `Mình muốn bán chiếc ghế công thái học, giá 800k, dùng được 6 tháng.`
   Expected: draft NM-* with price 800000. `ok` / `xác nhận` -> pending. Try
   `sửa giá 700k` or `sửa tiêu đề ...` before confirming; `hủy` cancels draft.
   If price/condition missing, supply the requested field; no invented values.
2. **Moderation** Log in BQL -> `/bql/listings`, inspect source and reasons,
   enter a review reason and explicitly confirm approval. Even low risk waits
   for this step. Sensitive/prohibited content cannot be approved.
3. **Publisher** `/bql/deliveries`: queued -> claimed -> sent only after a valid
   receipt. Verify exactly one formatted text post in the allowlisted group,
   real receipt equals saved sent_message_id, and another schedule tick does not
   duplicate it. Approved alone does not mean sent.
4. **Buyer** From an explicitly permitted test identity PM `tìm ghế`. The first
   generated workflow permits one tester; for a second tester deliberately add
   that verified ID to private/zalo-channel.json sender_ids, then clear the fromId
   filter in the SAME intake workflow. The adapter still enforces the explicit
   sender allowlist; other senders receive no reply. Keep one active inbound
   workflow/consumer. Restart the adapter after changing its allowlist.
   Expected approved/available listing in the same community, no seller identity.
5. **Safety** Submit `Mình muốn bán chiếc máy giặt, giá 800k, dùng 6 tháng, đặt cọc trước.`
   Confirm, inspect advisory suspicious flag. No job/group post until a human
   decision. Reject with reason and verify no delivery was created.

## E. Delivery ambiguity and fallback

- queued: DB job exists; claimed: a worker owns a five-minute lease.
- sent: ACK stored, with transport_mode=mock/deplao/unverified. Even a claimed
  Deplao receipt is an asserted transport receipt; independently verify the group
  for a live demonstration. Older ACKs without mode are unverified.
- failed: definitive non-send or operator reconciliation. No blind retries.
- unknown: timeout/missing receipt/expired claim; do not send again automatically.

Deplao's send node has no verified error edge. With continueOnError=false a thrown
send halts the graph; after five minutes the next claim or BQL delivery read marks
it unknown. Missing receipt on a completed node records unknown immediately.
ACK timeout may leave sent already committed, or claimed until expiry; refresh
and inspect, never replay the send node. A conclusive pre-send rejection can be
recorded using existing `/failure` with outcome=not_sent; do not classify a
network exception as proof of non-send.

For unknown: stop the old publisher, inspect the actual group/history and receipt,
then use the existing BQL reconciliation with a reason/evidence. Reconciliation
does not requeue. This avoids blind duplicates; it does not promise exactly-once
delivery from an external Zalo client. On connector failure continue with the
offline five-scene demo and explicitly say that no live send was verified.

## Deliberate limits

Text only. Attachments are not downloaded, understood, stored or published.
No Gemini fallback, guessed price, autonomous approval, individual BQL accounts,
automatic Zalo reconnect/login, group permission edits, old-message deletion,
sold group notices or retries. OpenAI extraction is optional and uses a bounded
validated schema; its risk flag is advisory, not a separate calibrated AI safety
classifier. Disabled/unavailable AI falls back to narrow Vietnamese patterns and
legacy commands. Conversations currently have no TTL/retention UI; protect the
private SQLite database. Search is keyword-based, approved and unsold only.
