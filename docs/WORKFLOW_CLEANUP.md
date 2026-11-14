# Workflow audit and safe cleanup

Recorded 14 November 2026 on branch `feat/vinhomes-sunrise-landing-bql-ui`.
Read-only tool: `.\.venv\Scripts\python.exe -m tools.workflow_inventory [--git-ref origin/main]`.
It redacts keys, numeric IDs, placeholders and local media paths before comparing
graphs with the canonical generator output. It never deletes, moves, imports or
prints credentials. **A JSON file on disk says nothing about what is imported or
enabled inside Deplao.**

## Target state (one of each, nothing competing)

| Role | Generated file (private, untracked) | Trigger / endpoint |
| --- | --- | --- |
| Text intake | `private/deplao-intake.json` | private text PM → adapter `:8001/intake` |
| Image intake (optional) | `private/deplao-image-intake.json` | private image PM → adapter `:8001/intake/image` |
| Publisher v2 | `private/deplao-publisher-v2.json` | schedule → `:8000/deliveries/claim` with `X-Publisher-Version: 2` |
| Channel manifest | `private/zalo-channel.json` | read by `run-local.ps1` / `run-intake.ps1`; not a workflow |

The generator refuses to overwrite any of these. Image intake is only written
with `--enable-images --image-metadata-verified --publication-mode photos_v2`.
The v1 text publisher (`build_publisher(version=1)`) is superseded: the v2
publisher sends single-text listings too.

## Inventory on this checkout (re-run, not assumed from the checkpoint)

The checkpoint recorded `private/local-config.json` and `private/market.db` on
the original machine (`C:\Users\Admin\...`). This checkout
(`C:\build-phase\neighbormarket-zalo-mvp`) has **no `private/` directory at all**,
so there are no generated exports, runtime configs or databases here to compare.

| Source | Class | Redacted fingerprint | Notes |
| --- | --- | --- | --- |
| `workflows/meo-meo-auto-reply-private.json` (tracked) | legacy-standalone-pm-responder | `748cad16786e494b` | Gemini auto-reply on every private text. No credentials inside. Not connected to the marketplace; it competes with text intake for the same PMs. |
| `origin/main:private/workflows/deplao-local-workflow.json` | legacy-intake | `a42026b178f6d685` | Calls `main`'s `/bridge/zalo`, which does not exist on this branch. No `$pageId` gate, no strict-binding check. |
| `origin/main:private/workflows/image-safety-workflow.json` | legacy-intake | `734471390a31d1c2` | Calls `main`'s `/bridge/zalo-image`; same shape as the one above, different endpoint. |
| `origin/main:private/workflows/group-publisher-workflow-v2.json` | legacy-publisher | `371f5e8c9f9d9d3c` | Calls `main`'s `/group-publications/*`; incompatible with `listing_deliveries`/`delivery_parts`. |
| `origin/main:private/workflows/README.md` | non-workflow | – | Template instructions for `main`. |

`main`'s templates were inspected via `git show` only. They were **not** imported,
and `main`'s `.gitignore` exceptions that track `private/workflows/` were **not**
adopted: this branch keeps all of `private/` ignored. `git ls-files private` is empty.

## Decisions

- **Deleted:** nothing. No file was proven redundant on this machine, and there
  was no private export to back up first.
- **Archived/moved:** nothing. The tracked Gemini example stays as a recovery
  reference until a replacement is verified live; its docs label it obsolete.
- **Kept untouched:** every credential, session, DPAPI blob, database, WAL/SHM
  and unknown file. The inventory reports these as `private-data`/`runtime-config`
  without parsing or printing them.
- **Not adopted:** `main`'s three templates (wrong endpoints, no account gate).

## Operator procedure for a machine that does have `private/`

1. Stop backend, adapter, Next.js and Deplao publishers. Run the inventory and
   keep its output (it contains no secrets).
2. Copy the whole `private/` directory to a dated backup **outside the repo**
   (for example `%USERPROFILE%\nm-private-backup-YYYYMMDD`). Do not commit it.
3. A file is safe to remove only if it is classed `duplicate` of a file you keep,
   or `superseded-publisher-v1` after `deplao-publisher-v2.json` exists and is
   verified. Keep every `unknown`, `runtime-config` and `private-data` file.
4. To regenerate, move old generated files into the backup (the generator will
   not overwrite them), then run the generator as in MENTOR_LIVE_DEMO.md.

## Deplao UI actions only the operator can do (not done here)

Deleting or moving JSON does **not** disable a workflow already imported into
Deplao. In the Deplao workflow list, for the Meo Meo account:

1. **Disable** "Meo Meo - Gemini - Auto Reply Private" (from the tracked example).
2. **Disable** any imported "Meo Meo - Local Market Backend TEST",
   "Meo Meo - Image Safety Intake TEST" and "Meo Meo - Publish Approved with
   Photos v2" (from `main`'s templates), and any older "NeighborMarket - Approved
   Publisher" (v1) import.
3. Enable at most: "NeighborMarket - Private Intake", optionally "NeighborMarket -
   Private Image Intake", and "NeighborMarket - Approved Photos Publisher v2" —
   only after the strict-binding gate in DEPLAO_COMPATIBILITY.md passes.
4. Never run two PM consumers (intake + Gemini) or two publishers at once: two
   publishers can claim the same outbox and the slower one will see a stale claim.

None of this has been performed or verified on an installed Deplao application.
