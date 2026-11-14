# Main Marketplace Integration Implementation Plan

> **For agentic workers:** Use executing-plans inline, with one final independent review.

**Goal:** Add private product images, snapshot-safe human review, ordered delivery parts and sold notices to the existing Sunrise application.

**Architecture:** Keep the target conversation, SQLite, listing_deliveries, authentication and Next.js UI. Adapt main's image normalization/moderation and message ideas; add child delivery_parts rather than group_posts. Retain legacy single-text mode; explicit photos_v2 enables cover/additional/code parts. All live graphs retain the strict engine gate.

**Tech Stack:** Existing Python/FastAPI/SQLite, Pillow 13.0.0, optional OpenAI moderation; Next.js/TypeScript/Zod.

**Spec:** User's Latest Marketplace Backend integration request (P0-P8), this audit records implementation decisions.

## P0 baseline

- Existing worktree: C:\Users\Admin\neighbormarket-zalo-mvp; branch feat/vinhomes-sunrise-landing-bql-ui. Clean, no branch creation or source merge.
- Target/base: fa86ad9877e104541378841b9dd67b0e33ee4f47; origin/main: d28faeefdf947d9c85fca4e173fe153b9b2a9e57 after fetch.
- Backend 70/70; frontend 6/6, TypeScript and lint pass before code changes.
- Reference main files read through git show, saved only under ignored work/main-reference. No runtime templates imported or executed.
- Reviewed Deplao source remains 2162f077d49f3b990121717fe6596fb3f0941e2f; installed application still unverified. Read DEPLAO_COMPATIBILITY.md and prior integration decisions.

## Matrix

| Feature in target | Main improvement | Decision | Schema/code implications | Risk and required tests |
| --- | --- | --- | --- | --- |
| Persistent conversations, revision guard, VND parser, optional OpenAI | Gemini multi-turn engine, epoch table | Keep target; only useful aliases/copy | No second engine/provider; hủy nháp alias | clarification/edit/cancel/legacy and VND regression |
| No images | images.py normalizes, stores privately, moderation + snapshot | Adapt into new ImageStore with existing DB callback | listing_images, image_events, image_reviews; private admin previews | size/pixels/MIME/EXIF, identity/scope, stale/concurrent review |
| Trusted text intake | CDN photo workflow | Adapt behind disabled-by-default image gate | /intake/image -> /image-events; trusted metadata; pinned IP/TLS fetch | SSRF, redirect, time/byte limits, no URL logs, context changes during fetch |
| Human listing review | manual image evidence/token | Add optional review fields | image_review_token/manual_image_review; immutable approved snapshot | pending blocks, stale token, manual reason, no post-approval mutation |
| One text delivery | cover/additional/code receipts | Adapt into target child parts | delivery_parts with stable IDs/order/token/receipt; parent contract retained | concurrency, duplicate ACK, partial failure, unknown reconciliation |
| Sold removes search | group sold notice | Adapt into same parent outbox as sold_notice part | unique parent/type/position; cancel unsent parts, retain receipts | duplicate sold, in-flight safety, never recall original |
| Next.js secure BFF | standalone admin HTML | Skip HTML; extend current BQL only | optional Zod images/parts; authenticated binary BFF | no client key, CSRF, community/image scope, old schemas |
| Strict account binding gate | permissive alternative workflows | Keep gate; extend canonical generator | verified sendImage filePath/message/attachment receipt; no branch convergence | exact source hash, graph schema, private paths, real receipt required |
| private ignored entirely | tracked sanitized private/workflows | Skip ignore exceptions | templates if needed outside private; preserve secrets/data | inventory/redacted graph comparison; archive before removal |

## Global constraints

- One authoritative database, NM-* lifecycle, mandatory BQL approval, one account/group.
- No group_posts, second dashboard, n8n, silent AI fallback provider or automatic uncertain retries.
- No real sends or paid model calls in automated tests; no secret/runtime data in Git.
- Existing worktree/branch only; normal push, preserve teammate changes and Golden Sunrise design.
- BQL preview is authenticated same-origin binary proxy, never an admin key in image URL.

## Review focus

1. Content/context changes during download or moderation: bind the original listing/revision and reject late attachment; mark old evidence stale.
2. Partial media success then lost ACK: stable part ID/token, no later part until acknowledged/reconciled, no resend of sent parts.
3. Sold while publication is unresolved: retain existing fail-closed in-flight restriction, cancel queued parts; only queue a notice when a public post has evidence.
4. Legacy queued/sent rows and old publishers: retain single-text API behavior; require X-Publisher-Version=2 for media or multipart work.
5. File/URL and BFF boundary: pinned global addresses, TLS/redirect/size deadlines, generated allowlisted local paths, admin-only image bytes.

## Tasks / execution ledger

- [x] P0 compare/audit/baselines and existing worktree verified.
- [ ] P2 tests first: private image processing, optional moderator and guarded bridge intake. Implement backend/images.py + image_fetch.py; mount routes through existing auth/DB; test red then green, commit.
- [ ] P3/P4 tests first: delivery_parts snapshots/order/receipts/reconcile and sold notices, improve compact Vietnamese messages. Implement backend/delivery_parts.py and adapt app/publisher/channels; legacy suite green, commit.
- [ ] P5 extend optional contracts/BFF/image review and delivery details; frontend unit + production HTTP checks; preserve landing/auth; commit.
- [ ] P6 extend one gated generator with image intake/publisher v2; inspect inventory; archive/remove only proven redundant files; document WORKFLOW_CLEANUP.md.
- [ ] P7 full backend/frontend/build, offline text + image demos, browser QA, independent security review and regression fixes.
- [ ] P8 update startup/config/live limits, scan staged files, logical commits and normal push to existing target branch.

Ruling: OpenAI remains the only configured cloud provider; Gemini is deferred because the target already covers persistent multi-turn extraction. This avoids two models/engines and leaves broader Gemini phrasing unsupported.

Ruling: Keep sold blocked during claimed/unknown publication, preserving the target's safety rule. A seller must wait for or request BQL reconciliation; this prevents a late cover post after a sold notice.

Ruling: Local inventory currently has only private/local-config.json and private/market.db; no generated private workflows to delete. The tracked independent Gemini example is retained for recovery and documented as obsolete/disabled, until a replacement has been verified live. No claims of active Deplao state can be made from files alone.

## Paused checkpoint — explicit user request, 14 November 2026

Implementation is approximately 65% of the requested scope. This is a checkpoint,
not a completed integration release. Resume only after the user says to continue.
Worktree/branch remains C:\Users\Admin\neighbormarket-zalo-mvp /
feat/vinhomes-sunrise-landing-bql-ui; no extra branch or worktree was created.

Implemented at checkpoint:

- Private images in the target SQLite DB, JPEG/PNG/WebP normalization, EXIF removal,
  size/pixel/count limits, optional OpenAI moderation with unavailable/error states,
  snapshot tokens, stale checks and reasoned BQL manual image review.
- Metadata-pinned image intake extension, disabled by default. CDN downloader pins
  validated global DNS addresses, retains TLS host validation, rejects redirects,
  bounds time/bytes and has no automatic retry. No URL logging.
- delivery_parts under listing_deliveries: immutable cover/additional/code
  snapshots, sequential claims/receipts, parent aggregation, unknown reconciliation,
  sold notices and cancellation of unsent parts. Legacy single-text mode retained.
- Vietnamese structured replies, hủy nháp alias and scoped NM-* detail lookup.
  Existing VND parsing already covers 500k, 1tr2 and 1,5 triệu.
- BQL image viewer/upload/recheck, manual evidence, optional Zod fields, same-origin
  authenticated binary BFF and per-part delivery details. No client admin key.
- Canonical generator has gated image intake and publisher v2 with verified
  sendImage filePath/message/attachment receipt fields. Runtime image flags need a
  validated private manifest. Strict account-binding gate remains mandatory.
- Text and image-inclusive offline demos both pass. Image demo explicitly uses a
  synthetic moderator stub and mock transport; it does not establish image model
  accuracy, Zalo connectivity or real publication.

Checkpoint verification: backend **90/90**, frontend **7/7**, TypeScript, ESLint,
Prettier and production build pass. Existing HTTP BFF regression is run before
checkpoint push; see docs/MAIN_INTEGRATION_CHECKPOINT.md for its result.

Still required on resume:

1. Extend production HTTP fixtures/tests for authenticated image upload/preview,
   image review tokens/manual evidence and multipart reconciliation; browser QA.
2. Broaden security/concurrency/media tests: pending/recheck races, interrupted
   moderation, failed/unknown cover recovery, lost ACK across parts, export paths
   and migration of old publication records. Perform independent code review.
3. Finish workflow redaction/comparison and safe consolidation report. No private
   workflow or imported Deplao definition has been deleted or modified.
4. Update full README, integration/mentor/frontend guides and .env.example with
   image configuration, photos_v2 startup and current file names. Existing guides
   still describe the previous text-only release; use the checkpoint document.
5. Explicitly decide supplemental photos for already-approved text-only listings;
   current APIs deliberately prevent any post-approval media mutation. Do not
   implement silent image replacement or imply that supplemental uploads work.
6. Complete full QA and normal push after affected fixes. All live Zalo evidence
   remains unverified; installed Deplao has not been patched or configured here.

Current new schema is additive: listing_images, image_events, image_reviews,
delivery_parts; parent delivery message_snapshot/snapshot_token and reconciliation
part_id. No group_posts, second DB, Gemini engine, n8n or dashboard was introduced.
