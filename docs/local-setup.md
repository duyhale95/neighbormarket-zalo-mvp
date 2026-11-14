# Cấu hình local và Deplao

## Backend

Tạo venv, cài requirements và chạy `pwsh -File .\run-local.ps1` như README. Ctrl+C để dừng. Không xóa private nếu muốn giữ dữ liệu/cấu hình.

Script đọc:

- `private/local-config.json`: bridge_key/admin_key, tự tạo lần đầu.
- `private/gemini-settings.json`: `{"model":"TEN_MODEL_DANG_DUNG"}` và `private/gemini-key.xml` (DPAPI). Hoặc dùng `-GeminiKeyFile`/`-GeminiModel`, env `GEMINI_API_KEY`/`GEMINI_MODEL`.
- `private/moderation-key.xml`: tạo bằng `pwsh -File .\setup-moderation.ps1`, nhập khóa mới vào ô ẩn.
- `private/group-settings.json`: đích nhóm/khu, tạo bằng builder nhóm.

Không cấu hình Gemini thì lệnh text xác định vẫn dùng được. Moderation thiếu cấu hình/lỗi không được coi là an toàn; BQL phải kiểm tra thủ công. `.env.example` chỉ là mẫu tên biến, script không tự đọc `.env`.

## Sinh workflow riêng tư

Sau khi chạy backend lần đầu để có local-config:

```powershell
.\.venv\Scripts\python.exe tools/build_local_workflow.py --sender-id ID_NGUOI_THU
.\.venv\Scripts\python.exe tools/build_image_workflow.py --sender-id ID_NGUOI_THU
.\.venv\Scripts\python.exe tools/build_group_workflow.py --group-id ID_NHOM --group-name "TEN_NHOM" --community demo
```

Builder nhóm lưu settings; restart backend sau khi đổi đích. Import:

- `private/deplao-local-workflow.json`
- `private/image-safety-workflow.json`
- `private/group-publisher-workflow-v2.json`

Chọn đúng Meo Meo, lưu và bật. Tắt publisher cũ khi chuyển v2. Chat/ảnh chỉ nhận ID thử theo mặc định; sửa From ID sau khi chốt phạm vi người dùng. Mở bộ lọc không đồng nghĩa đã xác minh cư dân thật.

Workflow chứa bridge key thật, chỉ giữ local. Không bật chatbot Gemini độc lập cũ song song vì nó không quản lý tin trong backend này.

## API bridge

- `POST /events`: JSON có event_id, community_id, sender_id, text, thread_type, is_self. Chỉ bridge tin cậy được gán identity/khu, không lấy từ lời nhắn cư dân.
- `POST /bridge/zalo`: text/plain prefix `NM-TEXT:\n`; headers `X-Sender-Id`, `X-Event-Id`, `X-API-Key` (bridge key). Prefix tránh Deplao parse nội dung chat thành JSON.
- `POST /bridge/zalo-image`: prefix `NM-IMAGE:\n` và URL ảnh đầu từ metadata; cùng headers. Chỉ tải CDN cho phép, pin IP, kiểm tra TLS, giới hạn tải/thời gian.
- `POST /group-publications/claim`: bridge key; v2 thêm `X-Publisher-Version: 2`. Không gọi claim thật chỉ để xem thử vì nó chuyển job sang sending.
- `POST /group-publications/{job_id}/ack`: token claim và message_id Zalo hợp lệ. HTTP thành công không tự chứng minh đã gửi tin.
- API listings/review/publish/image/recheck: admin key và scope community; dashboard gọi các API này.

Không đưa key vào URL. Giữ ID event thật khi retry. Inbound cache tránh tạo trùng dữ liệu; outbound có thể mất ack nên phải xem trạng thái uncertain và kiểm tra nhóm trước khi đăng lại.

## Nghiệm thu

1. Nhắn text bán món: bot hỏi thiếu, trả nháp.
2. Gửi ảnh trước xác nhận: dashboard có ảnh và kết quả safety.
3. Xác nhận: pending. BQL xem đúng phiên bản và duyệt.
4. Nhóm nhận ảnh/nội dung, ảnh bổ sung và mã riêng qua publisher v2.
5. Tìm từ khóa hoặc gửi mã: chỉ trả món cùng khu, đã duyệt, còn bán.
6. Chủ tin báo đã bán: loại khỏi tìm kiếm và thông báo nhóm nếu bài đã được gửi.

Nếu lỗi, kiểm tra lần lượt event Deplao, response backend, node gửi và receipt. Nút chạy thử không chứng minh Zalo thật. Không mở listener cạnh tranh Deplao.
