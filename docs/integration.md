# Hợp đồng tích hợp marketplace

## Trạng thái và giới hạn tin cậy

**Live bị khóa trên source Deplao stock đã khảo sát:** `getApi` có fallback
sang account khác. Generator yêu cầu engine strict binding đã review và xác
minh bản cài đang chạy; xem [DEPLAO_COMPATIBILITY.md](DEPLAO_COMPATIBILITY.md).
Patch được cung cấp để review, chưa áp dụng lên upstream hay ứng dụng cài máy.
Mock không phụ thuộc gate này và không có gửi thật.

Backend, adapter intake và outbox đã được kiểm thử bằng event và bộ gửi giả lập; **chưa xác minh Zalo thật, listener Deplao hoặc publisher trên ứng dụng đang cài**. Generator `tools/build_deplao_workflows.py` đối chiếu node/engine tại SHA ghi trong PARTNER_INTEGRATION_PLAN.md. `workflows/meo-meo-auto-reply-private.json` là chatbot Gemini độc lập, không nối backend marketplace; tắt khi bật intake mới. Không đưa key, cookie, token, nội dung PM thật vào Git. [MENTOR_LIVE_DEMO.md](MENTOR_LIVE_DEMO.md) có startup, import, mock và checklist bằng chứng live.

Bản source Deplao upstream đã khảo sát có thể lưu raw message, input/output node và HTTP header/body; không thể cam kết không log dữ liệu nhạy cảm khi dùng bản đó. Chỉ thử với dữ liệu giả cho đến khi kiểm chứng cách xử lý log và cấu hình thực tế. Các định danh, loại luồng, trạng thái tự gửi phải do connector đáng tin cậy lấy từ metadata Zalo; không lấy từ nội dung người dùng.

## Adapter intake

`backend.intake_bridge:from_environment` là adapter FastAPI không có database nghiệp vụ riêng, cung cấp `POST /intake` với header `X-Intake-Key`. Nó chỉ chuyển event vào backend hiện có. Cấu hình `BACKEND_URL`, `BRIDGE_API_KEY`, `INTAKE_API_KEY` khác bridge key, và `COMMUNITY_ID` ở runtime. `run-intake.ps1` đọc các giá trị từ private config sau khi generator đã chạy. Ví dụ cấu hình thủ công trong cửa sổ riêng sau khi backend khởi động:

```powershell
$env:BACKEND_URL = 'http://127.0.0.1:8000'
$env:COMMUNITY_ID = 'demo'
# Thiết lập BRIDGE_API_KEY từ private/local-config.json và INTAKE_API_KEY khác, giữ bí mật.
.\.venv\Scripts\python.exe -m uvicorn backend.intake_bridge:from_environment --factory --host 127.0.0.1 --port 8001
```

Connector phải POST JSON được serialize an toàn, gồm `message_id`, `sender_id`, `thread_id`, `thread_type` (`private` hoặc `group`), `is_self` boolean và `text`. Message ID phải ổn định qua retry, sender/thread phải lấy từ metadata, community do adapter cấu hình. Adapter bỏ qua tin tự gửi và tin nhóm, rồi gửi event tới backend. Connector chịu trách nhiệm trả đúng `reply` vào thread gốc; không gửi khi `ignored` hoặc reply rỗng. Việc dedupe xử lý backend không bảo đảm gửi reply PM đúng một lần.

Extension cùng `/intake`: `Content-Type: text/plain; charset=utf-8`, body là
`NM-TEXT:` + newline + nội dung gốc. Header `X-Zalo-Account`, `X-Zalo-Sender`,
`X-Zalo-Thread`, `X-Zalo-Message` phải là ID số từ trigger; `X-Zalo-Thread-Type`
là `0`/`1`, `X-Zalo-Self` là `true`/`false`. Khóa nằm trong `X-Intake-Key`,
không nằm URL/body. Account và tester được pin bởi cấu hình tin cậy; thiếu/sai
metadata bị từ chối. Event ID raw được hash có namespace account/sender/thread/msg
ổn định. Cộng đồng và source channel do adapter đặt, không lấy trong nội dung.
Body có giới hạn byte và ký tự; không nội suy text vào chuỗi JSON. Node reply
luôn gửi về `$trigger.threadId` gốc. 401/403/422 ở adapter không tạo tuyên bố đã lưu;
HTTP timeout/status=0 ở Deplao không được gửi reply thành công giả.

## Backend event và BQL

`POST /events` dùng `X-API-Key` là bridge key:

```json
{"event_id":"stable-message-id","community_id":"demo","sender_id":"sender-id","text":"ban Ghế | 500000 | đã dùng 6 tháng","thread_type":"private","is_self":false}
```

Backend cache theo community/sender/event ID. Lệnh `ban Tên món | Giá VND | Tình trạng` tạo draft, `xacnhan MÃ_TIN` chuyển pending, `tim từ khóa` chỉ tìm tin approved chưa bán, và `daban MÃ_TIN` do chủ tin gửi chuyển sold. Có thêm hội thoại tự nhiên, `ok`/`xác nhận` cho nháp hiện tại, `hủy [MÃ_TIN]`, `sửa giá 700k`, `sửa tiêu đề ...`. Context thiếu trường nằm trong bảng conversations cùng DB; chỉ khi đủ mới tạo listings draft. Cancelled không được xác nhận/tìm kiếm/xuất bản. Model chạy ngoài transaction; revision ngăn kết quả cũ hồi sinh nháp đã hủy/thay đổi. HTTP 401/404/409/422 được adapter chuyển thành thông báo an toàn; timeout báo chưa xác định kết quả. Có thể dùng Swagger tại `http://127.0.0.1:8000/docs` với dữ liệu giả.

BQL gọi `GET /listings?community_id=demo` và `POST /listings/MÃ_TIN/review` bằng admin key; body ví dụ `{"community_id":"demo","action":"approve","reason":"Đã kiểm tra"}`, hoặc action `reject` kèm lý do. BQL phải tự kiểm tra nội dung và `moderation_flags`; các mẫu nhạy cảm được phát hiện sẽ bị chặn approve. Bộ lọc là heuristic và không đảm bảo bắt mọi dữ liệu nhạy cảm.

Trước khi approve, cấu hình `ZALO_LEGIT_GROUP_ID` và `ZALO_COMMUNITY_ID`. `delivery_status: queued` nghĩa là đã tạo job trong transaction duyệt; `not_configured` nghĩa là approve thành công nhưng không có job vì thiếu group hoặc sai community. Không có backfill tự động; cần tin mới cho demo sau khi cấu hình. Reject không tạo job (`not_applicable`).

## Thống kê và audit

BQL có thể gọi `GET /stats?community_id=demo` bằng admin key để lấy `total`, `pending`, `approved`, `rejected`, `sold` và số delivery `sent` trong community. Đây là đếm trạng thái lưu trong backend; ACK giả lập cũng tạo delivery `sent` và không chứng minh đã đăng Zalo thật.

Backend ghi audit JSON với các trường metadata được chọn cho event, AI extraction, review và delivery; không cố ý đưa nội dung PM, key hay claim token vào các trường này. `event_id` và `correlation_id` trong audit là SHA-256 của event ID gốc để đối chiếu các bước. Mã băm ổn định không bảo đảm ẩn danh và có thể liên kết hoặc bị đoán khi ID gốc dễ đoán; bảo vệ log và không chia sẻ công khai. Logging này không thay thế đánh giá log của Deplao upstream.

## Delivery cho bridge đáng tin cậy

- `POST /deliveries/claim`, bridge key: nhận một job approved cùng `delivery_id`, `claim_token`, `group_id`, `message`; 204 nghĩa là không có job có thể claim. Group lấy từ cấu hình tin cậy, không lấy từ PM.
- `POST /deliveries/{id}/sent`, bridge key: gửi `claim_token` và tùy chọn `sent_message_id` khi có bằng chứng gửi thành công. Khi mock, ACK chỉ ghi nhận mô phỏng.
- `POST /deliveries/{id}/failure`, bridge key: gửi `claim_token`, `outcome` là `not_sent` hoặc `unknown`, và `error` ngắn. Chỉ dùng `not_sent` nếu chắc chắn chưa gửi; khi không chắc, dùng `unknown`. Claim hết hạn cũng thành `unknown`, không tự retry.
- `GET /deliveries?community_id=demo`, admin key, hoặc `GET /deliveries/{id}`, bridge key: xem trạng thái. BQL đối soát bằng `POST /deliveries/{id}/reconcile`, admin key, với `decision: sent` hoặc `not_sent` và `reason`; `not_sent` thành `failed`, không tự đưa lại vào hàng đợi.

## Ảnh sản phẩm (private) và kiểm duyệt ảnh

Trạng thái: **đã cài và kiểm thử bằng dữ liệu tổng hợp**; moderation thật
(OpenAI) **chưa từng được gọi**; nhận ảnh từ Zalo thật **chưa xác minh**.

- `POST /listings/{id}/images` (admin key): JSON `{"community_id","image_base64"}`,
  body tối đa 6 MiB. Nhận JPEG/PNG/WebP tĩnh ≤ 4 MiB, ≤ 16 triệu pixel, tối đa
  5 ảnh/tin, chỉ khi tin `draft`/`pending`. Ảnh được chuẩn hóa JPEG ≤ 1600px,
  bỏ EXIF/metadata, lưu trong SQLite (`listing_images`). Trùng nội dung trả ảnh cũ.
- `GET /images/{id}?community_id=` (admin key): bytes JPEG, `Cache-Control: private,
  no-store`, sandbox CSP. Sai community → 404. BQL xem qua BFF `/api/bql/images/{id}`.
- `POST /images/{id}/recheck?community_id=` (admin key): tạo phiên bản mới; kết quả
  moderation đến muộn của phiên bản cũ bị bỏ. Ảnh `pending` < 60 giây không recheck
  được; sau 60 giây được coi là treo và có thể recheck. Tin đã duyệt: 409.
- `POST /image-events` (bridge key): chỉ khi image intake bật qua manifest; xem dưới.
- Trạng thái ảnh: `clear`, `flagged`, `pending`, `error`, `unavailable`, `stale`
  (nội dung tin đổi sau khi kiểm tra). Moderation tắt/không có key → `unavailable`.
  Model/network chạy **ngoài** transaction ghi SQLite (có test kiểm chứng).
- `GET /listings` thêm `images[]` và `image_review_token` (SHA-256 của nội dung tin +
  ID/digest/trạng thái/phiên bản ảnh). Approve tin có ảnh phải gửi token hiện tại;
  token cũ → 409. Ảnh `pending` luôn chặn duyệt. Ảnh khác `clear` cần
  `manual_image_review: true` và lý do; bằng chứng lưu vào `image_reviews`.
  `clear` chỉ là "chưa bị gắn cờ", không xác minh hàng thật.

Image intake qua adapter: `POST /intake/image`, `text/plain`, body
`NM-IMAGE:\n<URL từ metadata trigger>`, cùng header metadata như text intake.
Không bao giờ lấy URL/danh tính từ nội dung PM. Mặc định trả 503. Downloader chỉ
nhận `https://photo-zalo.zadn.vn` và `photo-stal-N.zdn.vn` (cố ý từ chối `*.zcdn.me`),
kiểm tra mọi DNS answer là địa chỉ global, pin IP đó khi kết nối nhưng giữ SNI/TLS
hostname, không redirect/proxy, ≤ 4 MiB, ~8 giây, tối đa 2 tải song song, không log URL.
Giới hạn đã biết: tra DNS (`getaddrinfo`) không có timeout riêng; resolver treo có thể
giữ 2 slot tải tới khi hệ điều hành hết hạn, làm intake ảnh tạm báo bận (không ảnh
hưởng text hay an toàn).
Ảnh chỉ gắn vào **bản nháp chưa xác nhận** của đúng người gửi; nếu nháp đổi trong lúc
tải, ảnh bị từ chối. Gửi ảnh sau khi đã xác nhận/duyệt nhận được câu trả lời rõ ràng
là không bổ sung được (không âm thầm gắn).

**Giới hạn có chủ ý — ảnh bổ sung cho tin đã duyệt:** không hỗ trợ. Làm an toàn cần
revision mới + BQL duyệt lại + chỉ enqueue phần mới; chưa triển khai. Người bán tạo
tin mới nếu cần đăng kèm ảnh.

## Publisher nhiều phần (`delivery_parts`) và thông báo đã bán

Trạng thái: **đã cài, kiểm thử bằng mock transport**; chưa gửi ảnh thật lên Zalo.

`ZALO_PUBLICATION_MODE=photos_v2` (mặc định `single`) làm approval **mới** tạo các
phần con dưới đúng một `listing_deliveries`: `cover_photo_with_caption` (hoặc
`post_text` nếu không có ảnh), `additional_photo`…, `listing_code`. Nội dung từng
phần là snapshot lúc duyệt; ảnh được kiểm digest khi export.

- Claim với `X-Publisher-Version: 2` trả thêm `part_id`, `part_type`, `has_image`,
  `image_path` (file JPEG trong `private/group-media/`, tên = part ID). Thứ tự bắt
  buộc: phần sau chỉ được claim khi mọi phần trước `sent`/`cancelled`.
  Snapshot/ảnh/đường dẫn export thay đổi (kể cả symlink/junction ra ngoài) → phần
  `failed` (`stale_snapshot`/`unsafe_media`), không gửi.
- Publisher v1 (không header) chỉ nhận job không có phần con; job nhiều phần không
  còn chặn hàng đợi v1. Publisher v2 cũng gửi tin `single` (tự tạo một `post_text`).
- `POST /deliveries/{id}/sent|failure` thêm `part_id`; ACK phần bắt buộc có receipt
  rõ (`mock-*` hoặc msgId số Deplao). ACK lặp cùng receipt là idempotent; receipt
  khác hoặc token/part không khớp → 409. Lease hết hạn → phần `unknown`; ACK đến muộn
  bằng đúng token vẫn chuyển phần đó `sent` và chỉ mở phần kế tiếp.
- `POST /deliveries/{id}/reconcile` cho job nhiều phần **bắt buộc** `part_id` của
  đúng phần `unknown` (thiếu → 422, sai → 409) và `sent_message_id` khi `sent`.
  `not_sent` → phần `failed`, các phần sau bị chặn; không tự requeue.
- Trạng thái cha: `unknown` > `claimed` > `failed` > `queued` > `sent` > `cancelled`.
  Mỗi phần giữ receipt riêng; `GET /deliveries` trả `parts[]`.
- `daban`: bị chặn khi job đang `claimed`/`unknown` (giữ quy tắc cũ). Hủy các phần chưa
  gửi; nếu bài gốc đã có receipt thì tạo **một** `sold_notice` (position 1000), kể cả
  với job `single` cũ đã `sent`. Không thu hồi/xóa bài gốc trên Zalo.

## Backward-compatible schema extensions

- Event adds optional `source_channel`: legacy (default), deplao, mock. Only a
  trusted bridge can assert it; this is provenance, not measured connection health.
- GET listings preserves all old fields including JSON-string moderation_flags.
  Adds source_channel and nullable moderation object (risk_score, risk_level,
  categories, reason, policy_version, model_version, requires_review=true,
  ai_status, score_calibrated=false). Null reports mean legacy rows, not safe rows.
- Moderation uses rules plus optional existing OpenAI extraction risk signals.
  No second model safety call, no calibrated fraud probability, no auto-approval.
  Privacy/prohibited rules block approval and publication even for legacy records.
- GET deliveries adds transport_mode (default unverified). ACK/failure accept
  optional transport_mode=mock/deplao/unverified; explicit ACK modes require a
  matching receipt (mock-* or numeric Deplao msgId). Older ACKs remain accepted
  as unverified. Reconciliation records manual provenance and never requeues.
- SQLite only adds tables/columns: conversations, listing_images, image_events,
  image_reviews, delivery_parts; listing_deliveries.message_snapshot/snapshot_token;
  delivery_reconciliations.part_id. Migration is idempotent, preserves old queued
  and sent rows (tested), and does not import partner DBs or create group_posts.
- Next.js Zod accepts both old and extended responses. Authentication, same-origin
  mutation checks and server API-key handling are unchanged.

Generated publisher v2 (`private/deplao-publisher-v2.json`): schedule -> pinned
account -> claim (v2 header) -> group/ID/token/part checks -> `HasPhoto` branch:
photo parts check the export path against `private/group-media/<32 hex>.jpg` and
use `zalo.sendImage` (filePath + caption), other parts use one text send -> each
branch has its own real-mode/receipt check and its own ACK/unknown node, so
skips never converge. One part per schedule tick. A thrown send halts Deplao and expires to unknown
after five minutes; there is no verified error edge. No automatic retry or requeue.
Keep all workflow inputs/logs private. Source verification is not live verification;
complete the manual checklist before claiming a real group post succeeded.
