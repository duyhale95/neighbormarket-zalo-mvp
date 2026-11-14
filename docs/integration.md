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
- SQLite only adds conversations and missing columns; migration is idempotent,
  preserves old records and does not import partner DBs or create group_posts.
- Next.js Zod accepts both old and extended responses. Authentication, same-origin
  mutation checks and server API-key handling are unchanged.

Generated publisher: schedule -> pinned account -> existing claim -> group/ID/token
checks -> one text send -> real-mode/receipt checks -> existing sent/failure API.
No extra code-only group post. A thrown send halts Deplao and expires to unknown
after five minutes; there is no verified error edge. No automatic retry or requeue.
Keep all workflow inputs/logs private. Source verification is not live verification;
complete the manual checklist before claiming a real group post succeeded.
