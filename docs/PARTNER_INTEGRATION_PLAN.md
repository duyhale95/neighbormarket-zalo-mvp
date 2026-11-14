# Partner workflow integration — design and execution record

## P0 baseline (14 November 2026)

- Target UI base: `bda038330a9e39fb8164b77d52286a6518617bc9`.
- Partner VHR-07 main: `71ea945a601995a8c5733b5a0856b125e25a06a7`.
- Alternative marketplace: `47073ea021397ed072d0fc3056d095cd029b6ff4`.
- Deplao Builder: `2162f077d49f3b990121717fe6596fb3f0941e2f`.
- Target baseline: 37 backend tests, 4 frontend security tests and 24 production
  HTTP checks pass. TypeScript check passes. Source checkouts are read-only reference inputs, never executed
  as another marketplace service. No partner logging/grade hooks are imported.
- Existing tables: listings, events, reviews, listing_deliveries,
  delivery_reconciliations. Existing additive migration: moderation_flags.
- Authoritative contracts: `/events` (bridge key), `/intake` (separate trusted
  adapter with intake key), `/listings`, `/stats`, review and reconciliation
  (admin key), claim/sent/failure/status (bridge key). BQL Zod fields and BFF
  remain authoritative; no second login or public admin key is introduced.

## Ownership and approaches

Implement native, small modules in the target and adapt reviewed algorithms.
Running the partner application would split data and authorization; merging
the alternative branch would replace the existing outbox and frontend. Both
are excluded by the brief. The target SQLite database owns listings, event
deduplication, conversation context, review and publication state.

Private text goes through Deplao's verified trigger metadata to the existing
intake adapter, then `/events`. Raw text is sent with a fixed non-JSON prefix;
metadata/secret use headers. The adapter scopes community/account from trusted
configuration. Publication consumes the existing outbox, pins the target group
in the generated graph, validates receipt syntax, and never retries uncertain
sends. Model work runs outside database write transactions. All listings,
including low-risk ones, must be explicitly confirmed and reviewed by BQL.

| Partner feature | Source file | Target module | Decision | Reason |
| --- | --- | --- | --- | --- |
| Strict inbound metadata | channels/zalo.py | backend/channels.py | Adapt | Personal account schema differs from Bot Platform |
| Polling/getUpdates | channels/poller.py | none | Skip | Deplao is the only inbound consumer |
| Draft edit/confirm/cancel | services/posting.py | backend/conversation.py | Adapt | Preserve NM IDs and existing lifecycle |
| Vietnamese prices | services/vnd.py, text.py | backend/vnd.py | Reuse/adapt, MIT notice | Pure parsing, no guessed prices |
| Rules before AI | services/moderation.py, pii.py | backend/moderation.py | Adapt | Advisory risk plus hard privacy/prohibited gate |
| Auto-publish low risk | services/moderation.py | none | Skip | Human approval is mandatory |
| Review decisions | services/reviewflow.py | existing app review | Keep target | Atomic outbox and admin authentication |
| Search/commands | services/commands.py, search.py | existing events/search | Adapt aliases only | One scope and visibility policy |
| AI schemas/deadlines | services/safe_ai.py | existing ai.py | Keep target | Partner AI uses stubs; target OpenAI is optional |
| Direct group sends | services/posting.py | backend/publisher.py | Rewrite | Durable target outbox, ambiguity handling |
| Deplao text generator | alternative tools/build_local_workflow.py | tools/build_deplao_workflows.py | Adapt | Existing /intake, no second business API |
| Group generator | alternative tools/build_group_workflow.py | same generator | Adapt | Existing delivery endpoints, one text post |
| Natural context revisions | alternative backend/natural.py | conversation.py | Adapt idea | DB revision protects stale AI results |
| Gemini provider | alternative backend/ai_text.py | none | Defer | Use target configured OpenAI; deterministic fallback |
| Image safety | alternative backend/images.py | none | Defer | Unverified live text connector; no image download |
| Console/schema/hooks | partner src/api, db, hooks | none | Skip | No parallel dashboard/database/telemetry |

## Explicit mismatch decisions

- Bot Platform token (`bot-api.zaloplatforms.com`) is not a Deplao personal
  session. No Bot Platform poller is enabled or implemented in this iteration.
- Partner integer IDs map conceptually to target `NM-*`; no source DB import.
- Partner published maps to target approved, never proof of send. Partner
  in_review/pending_moderation map to pending, always BQL gated.
- Incomplete context is stored separately in the same SQLite DB; complete drafts
  use existing listings. Cancelled drafts stay private and cannot be confirmed.
- Partner direct send and alternative group_posts are replaced by
  listing_deliveries. Approval/enqueue stays one transaction, one listing/group.
- BQL keeps current password session/BFF and server-side X-API-Key handling.
- Moderation scores are advisory, uncalibrated, never probabilities or automatic
  approval thresholds. Rule-blocked privacy/prohibited content cannot be approved.
- Default live publishing remains off until trusted local configuration records
  human policy validation. Mock tests never send real messages or call paid AI.

## Deplao source findings and limits

WorkflowEngineService.ts flattens `msg.data.uidFrom/msgId/content`, outer
`threadId/type/isSelf`, and account `zaloId`. Trigger private type is string
`0`; ignoreOwn=true; messageTypes=[text]. HTTP parses body as JSON first,
then sends raw string on parse failure; fixed `NM-TEXT:\n` prevents accidental
JSON interpretation. Template rendering is one pass, not JSON escaping.
HTTP outputs status/data; network errors are status=0. IF uses true/false
edge handles; others default. Cron uses cronExpression/timezone. sendMessage
returns msgId (from result.message.msgId); `continueOnError=true` may still
return success=true, so it MUST be false. Simulate mode does not send HTTP or
Zalo and is not evidence. A thrown send stops the graph: no invented error
edge. Claim expiry becomes unknown; BQL must reconcile after stopping/checking
the old worker. Deplao stores rendered HTTP input/output and logs message
snippets upstream: keep its local logs/exports private; do not upload them.

## Implementation sequence / ledger

1. [x] P0: read sources, record refs/contracts, baseline and design.
2. [x] P1: channel models + safe text/plain /intake extension, generator and
   listener diagnostics. Tests: identity, account binding, Unicode/injection,
   self/group ignoring, backend error and event deduplication.
3. [x] P4: mock publisher + generated schedule/claim/allowlist/send/ACK graph.
   Tests: unique claim, receipt/unknown/failure, no rejected/sold publication,
   no resend after ACK loss, graph schema and secret output confinement.
4. [x] P3: typed moderation report, rules + optional advisory model signals;
   additive migration and mandatory review/recheck at publication boundary.
5. [x] P2: one persistent sender/community conversation, grounded Vietnamese
   parsing, clarification/edit/cancel/confirm, revision checks around AI calls.
6. [ ] P7: full offline mentor demo and security/concurrency regressions.
7. [ ] P5: optional report/source fields in Zod and current BQL details; no
   landing or authentication redesign. Check old schemas and HTTP suite.
8. [ ] P6: text only; attachments explicitly unsupported, no remote fetch.
9. [ ] P8: review, docs/config, baseline/regression/build checks, secret scan,
   logical commits, push only feat/integrate-partner-zalo-workflow.

P1/P4/P3 verification: 52/52 backend tests pass, including new parser, graph,
publisher and moderation tests. No outbound network/model call in these tests.
The model moderation layer reuses optional extraction risk signals; there is no
separate paid moderation request or calibrated score. Live send exceptions halt
the Deplao graph and become unknown on lease expiry (documented engine limit).

P2 verification: 58/58 backend tests pass. Natural demo text, restart-persistent
clarification, sender/community isolation, edit/cancel/confirm and legacy
commands pass. A blocked model call permits a concurrent cancellation and its
late result is rejected by the stored revision. OpenAI remains the only cloud
provider; deterministic Vietnamese patterns run offline when disabled or failed.
No Gemini/stub provider is silently selected. Incomplete context has no listing
record; cancelled complete drafts remain as private `cancelled` records.

Each implementation step is tested before and after the change. Final evidence
and any deviations are recorded here and in MENTOR_LIVE_DEMO.md. Real listener,
PM reply, group rights and send receipt remain **unverified** until an operator
performs the separate live checklist. A simulator ACK is always labelled mock.
