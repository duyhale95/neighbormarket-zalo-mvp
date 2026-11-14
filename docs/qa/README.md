# BQL media QA screenshots — SYNTHETIC DATA ONLY

Every screenshot in this folder was produced by `frontend/tests/browser_qa.py`
against the disposable fixture in `frontend/tests/backend_fixture.py`:

- Listings, sellers and IDs are invented; images are solid-colour squares.
- The image "moderator" is a colour-keyed stub (`SYNTHETIC-QA-STUB`), not OpenAI.
- Receipts such as `mock-fixture-part-1` come from mock ACKs. Nothing was sent to Zalo.
- Each image carries a red "DỮ LIỆU GIẢ LẬP" banner injected by the QA script.

| File | What it shows |
| --- | --- |
| `bql-image-review-{360,768,1440}.png` | Review dialog: private thumbnails via the BFF, clear/unavailable labels, manual evidence checkbox |
| `bql-delivery-parts-{360,768,1440}.png` | Delivery monitor with expanded per-part status, receipts and errors |
| `bql-part-reconcile-1440.png` | Reconciling one unknown cover part, with the part named and receipt required |

Regenerate after `npm run build` (Edge must be installed; Playwright is a QA-only tool):

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe frontend\tests\browser_qa.py --out docs\qa
```
