# Hợp đồng tích hợp marketplace

## Trạng thái và giới hạn tin cậy

Backend, adapter intake và outbox đã được kiểm thử bằng event và bộ gửi giả lập; **chưa xác minh Zalo thật, listener Deplao hoặc connector/publisher tự động**. `workflows/meo-meo-auto-reply-private.json` là chatbot Gemini độc lập, không nối backend marketplace. Không đưa key, cookie, token, nội dung PM thật vào workflow hoặc Git. [DEMO.md](DEMO.md) có kịch bản mock và hướng dẫn kiểm tra listener.

Bản source Deplao upstream đã khảo sát có thể lưu raw message, input/output node và HTTP header/body; không thể cam kết không log dữ liệu nhạy cảm khi dùng bản đó. Chỉ thử với dữ liệu giả cho đến khi kiểm chứng cách xử lý log và cấu hình thực tế. Các định danh, loại luồng, trạng thái tự gửi phải do connector đáng tin cậy lấy từ metadata Zalo; không lấy từ nội dung người dùng.

## Adapter intake

`backend.intake_bridge:from_environment` là ứng dụng FastAPI riêng, cung cấp `POST /intake` với header `X-Intake-Key`. Nó chưa được nối tự động với Deplao. Cấu hình `BACKEND_URL`, `BRIDGE_API_KEY`, `INTAKE_API_KEY` khác bridge key, và `COMMUNITY_ID` ở môi trường runtime. Ví dụ chạy trong cửa sổ riêng sau khi backend đã khởi động:

```powershell
$env:BACKEND_URL = 'http://127.0.0.1:8000'
$env:COMMUNITY_ID = 'demo'
# Thiết lập BRIDGE_API_KEY từ private/local-config.json và INTAKE_API_KEY khác, giữ bí mật.
.\.venv\Scripts\python.exe -m uvicorn backend.intake_bridge:from_environment --factory --host 127.0.0.1 --port 8001
```

Connector phải POST JSON được serialize an toàn, gồm `message_id`, `sender_id`, `thread_id`, `thread_type` (`private` hoặc `group`), `is_self` boolean và `text`. Message ID phải ổn định qua retry, sender/thread phải lấy từ metadata, community do adapter cấu hình. Adapter bỏ qua tin tự gửi và tin nhóm, rồi gửi event tới backend. Connector chịu trách nhiệm trả đúng `reply` vào thread gốc; không gửi khi `ignored` hoặc reply rỗng. Việc dedupe xử lý backend không bảo đảm gửi reply PM đúng một lần.

## Backend event và BQL

`POST /events` dùng `X-API-Key` là bridge key:

```json
{"event_id":"stable-message-id","community_id":"demo","sender_id":"sender-id","text":"ban Ghế | 500000 | đã dùng 6 tháng","thread_type":"private","is_self":false}
```

Backend cache theo community/sender/event ID. Lệnh `ban Tên món | Giá VND | Tình trạng` tạo draft, `xacnhan MÃ_TIN` chuyển pending, `tim từ khóa` chỉ tìm tin approved chưa bán, và `daban MÃ_TIN` do chủ tin gửi chuyển sold. Các HTTP 401, 404, 409 và 422 được adapter chuyển thành thông báo an toàn; timeout báo chưa xác định kết quả. Có thể dùng Swagger tại `http://127.0.0.1:8000/docs` với dữ liệu giả.

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

Không có workflow publisher Deplao được xác thực: chỉ dùng mock cho đến khi kiểm chứng metadata, JSON escaping, node mapping, gửi đúng group và ACK thực tế. Tài liệu và ví dụ hiện không cung cấp bằng chứng live. Xem [DEMO.md](DEMO.md) cho kịch bản và điều tra listener.
