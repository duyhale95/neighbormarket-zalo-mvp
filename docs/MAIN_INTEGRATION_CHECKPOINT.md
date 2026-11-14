# Main integration — status after resume

Branch: `feat/vinhomes-sunrise-landing-bql-ui`. Base before integration:
`fa86ad9877e104541378841b9dd67b0e33ee4f47`. Source reviewed:
`d28faeefdf947d9c85fca4e173fe153b9b2a9e57` (origin/main). Paused checkpoint:
`1578648279fd2a136514345f20afb98ea7618262`. Resumed 14 November 2026 on a
different Windows checkout (`C:\build-phase\neighbormarket-zalo-mvp`); the
original `C:\Users\Admin\...` worktree does not exist there. No new branch or
worktree was created; `main` was not merged or cherry-picked.

See MAIN_INTEGRATION_AUDIT.md for scope/decisions and WORKFLOW_CLEANUP.md for
the workflow inventory.

## Verified on resume (synthetic data, mocks only)

| Check | Checkpoint | After resume |
| --- | --- | --- |
| Backend unittest | 90/90 | **112 run, 111 pass, 1 skipped** (file-symlink test needs a privilege Windows did not grant; the junction variant of the same guard runs and passes) |
| Frontend unit (tsx) | 7/7 | 7/7 |
| TypeScript, ESLint, Next.js production build | pass | pass |
| Prettier | pass | pass on committed LF content (`--end-of-line auto` on this CRLF checkout) |
| Production HTTP BFF checks | 27/27 | **63/63** (36 new media/multipart checks) |
| Browser QA, Edge 157 headless | not done | **38/38** at 360/768/1440 px; screenshots in [docs/qa/](qa/README.md) |
| Offline text demo | pass | pass: 5 scenes, 1 mock group message |
| Offline image demo | pass | pass: cover, extra photo, code, sold notice; 4 distinct mock receipts; no resend |

No real Zalo message, Deplao login/import, OpenAI moderation call or paid model
call was made. Mock receipts and HTTP 200s are not evidence of real delivery.

## Fixed on resume

- **v1 publisher head-of-line block.** After a sold notice added parts to an old
  single-mode delivery, `/deliveries/claim` without `X-Publisher-Version: 2`
  selected that parent first and returned 204 forever, stalling every later text
  job. v1 claims now skip parents that have parts.
- **Multipart reconcile without `part_id`** was accepted. It now returns 422; a
  wrong part returns 409. The BFF/UI already sent the part ID.
- **Independent review (confirmed):** v2/multipart claims skipped the claim-time
  privacy/prohibited re-check that v1 had. Since the generated publisher is always
  v2, a rule tightened after approval would not stop publication. The check now runs
  for every path before parts are created/claimed (sold notices excepted).
- Review hardening: export re-validates an existing file entry against the media
  root; a late v1 ACK retry after sold is replayed instead of 409. Known, unfixed:
  DNS lookup has no own timeout (can hold the 2 download slots; availability only).
- Reconcile dialog now names the part (Vietnamese labels) and requires its receipt.
- Image intake replies to a photo sent after confirmation (or invalid image) with
  a fixed, specific message instead of the generic failure.

## Decisions

- Supplemental photos for already-approved listings: **not implemented.** It needs
  a revision + BQL re-review flow that enqueues only new parts; until then uploads,
  rechecks and Zalo photos after confirmation are refused explicitly.
- Workflows: nothing deleted or archived (no private exports on this machine).
  `main`'s `private/workflows` templates are incompatible and not adopted.

## Runtime defaults (unchanged)

`ZALO_PUBLICATION_MODE=single`, `IMAGE_MODERATION_ENABLED=false`,
`ZALO_IMAGES_ENABLED=false`. `photos_v2` applies to new approvals only. Live
image intake additionally needs the private manifest from the generator with the
strict engine hash, `images_enabled` and `image_metadata_verified`. The
DEPLAO_COMPATIBILITY.md gate still refuses the stock Deplao engine.

## Still unverified (requires an operator on the real machine)

Meo Meo connected; real PM received/replied; photo metadata on the installed
build; Meo Meo's send rights in Legit; real text/photo group posts and receipts;
DB ACK matching a real receipt; OpenAI moderation responses.
