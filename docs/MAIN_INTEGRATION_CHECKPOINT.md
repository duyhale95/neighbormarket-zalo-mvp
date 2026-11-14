# Main integration — paused checkpoint

Paused on the user's explicit request on 14 November 2026. Continue coding only
when the user resumes. Branch: feat/vinhomes-sunrise-landing-bql-ui.
Base: fa86ad9877e104541378841b9dd67b0e33ee4f47.
Source reviewed: d28faeefdf947d9c85fca4e173fe153b9b2a9e57 (origin/main).

See MAIN_INTEGRATION_AUDIT.md for the implemented scope and exact remaining tasks.
This checkpoint preserves working code; comprehensive media HTTP/browser QA,
workflow cleanup and final independent review remain unfinished.

## Verified checks

- Backend: 90 tests pass, zero failures.
- Frontend: 7 unit tests pass, zero failures; TypeScript, ESLint, Prettier pass.
- Next.js production build passes.
- Existing production HTTP BFF regression: **27/27 pass**, zero failures.
- Offline text demo: 5 scenes pass, one simulated group text message.
- Offline image demo: cover + additional image + listing code + sold notice,
  four distinct mock receipts; sold listing removed from buyer search; no resend.
- No real Zalo message, Deplao login or paid extraction request was performed.

## Reproduce the checkpoint locally

Use an existing environment; do not recreate an active .venv:

```powershell
Set-Location C:\Users\Admin\neighbormarket-zalo-mvp
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.offline_demo
.\.venv\Scripts\python.exe -m tools.offline_media_demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The new dependency is Pillow==13.0.0. The media demo uses a synthetic moderator
stub, not OpenAI/image understanding. Both demos use temporary data and send no
real messages. Optional model/CDN paths are mocked in automated tests.

Runtime defaults remain single-text publication and disabled Zalo image intake.
`ZALO_PUBLICATION_MODE=photos_v2` selects ordered cover/extra/code jobs for NEW
approvals. It does not automatically republish old listings or enable Deplao.
Set it before starting the existing run-local.ps1 if testing new media jobs.

Image moderation is disabled unless IMAGE_MODERATION_ENABLED=true and the private
IMAGE_MODERATION_API_KEY is configured; IMAGE_MODERATION_MODEL defaults to
omni-moderation-latest. Missing key produces unavailable, never clear. The API
shape was checked against [official OpenAI documentation](https://developers.openai.com/api/reference/resources/moderations/methods/create);
no real moderation call was performed here. Gemini was not added.

Live image intake additionally requires the generator's strict-source/build and
human-policy attestations, --enable-images --image-metadata-verified and
--publication-mode photos_v2. New generated publisher filename is
private/deplao-publisher-v2.json, image intake private/deplao-image-intake.json.
Existing files are never overwritten. Do not enable either graph before the
installed build/account/photo metadata/group rights are actually verified.
The existing DEPLAO_COMPATIBILITY.md gate still applies; stock source is refused.

BQL image previews use authenticated /api/bql/images/{id}, with HttpOnly session
and no admin key in the URL/browser. Existing login/landing design is preserved.
For unclear/stale image evidence, inspect each image and explicitly check manual
review with a reason; pending images always block approval. Approved images
cannot be uploaded/rechecked silently. Sent delivery parts are not replayed.

Private local-config.json/market.db are untouched; there is no new runtime
workflow export in private/. No imported Deplao settings were changed.
