# NeighborMarket Zalo MVP

Trợ lý chợ cư dân hoạt động qua chat riêng Zalo; quản trị qua dashboard.

## Bắt đầu chạy backend MVP

Đã có backend local cho tạo nháp, xác nhận, BQL duyệt/từ chối, tìm tin và báo đã bán. Đây là nền nghiệp vụ độc lập; chưa phải demo Zalo end-to-end. Không cần Supabase hoặc Gemini key để chạy các bước thử bên dưới.

Yêu cầu Python 3.11+ và PowerShell 7 cho script khởi động.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
pwsh -File .\run-local.ps1
```

Mở [API thử nghiệm local](http://127.0.0.1:8000/docs). Script tạo hai khóa thử khác nhau trong `private/local-config.json` (đã gitignore). Điền `bridge_key` ở ô `x-api-key` khi gọi `/events`, `admin_key` khi gọi API xem/duyệt tin. Không gửi khóa vào chat hoặc GitHub. API docs là công cụ thử, chưa phải dashboard BQL.

Đọc [hướng dẫn thử và hợp đồng tích hợp](docs/integration.md), [brief/PRD và UI flow](docs/brief-prd.md), [kế hoạch triển khai](docs/superpowers/plans/2026-11-14-marketplace-backend.md).

```powershell
python -m unittest discover -s tests -v
```

Trạng thái: SQLite, lệnh text xác định và tìm kiếm từ khóa; chưa có AI extraction, xử lý ảnh, Supabase/pgvector, login BQL hoặc deploy VPS.

## Đã làm
- Chốt hướng MVP trên Zalo cá nhân, sử dụng Deplao và Gemini.
- Tạo trợ lý Meo Meo và workflow nhận tin → Gemini → trả lời.
- Chạy thử thủ công workflow thành công.
- Chuẩn bị workflow trả lời tin nhắn văn bản riêng, không cần lệnh /chat.

## Đang làm
- Đã có bản brief/PRD và UI flow đầu tiên trong docs; tiếp tục lấy phản hồi.
- Tiếp theo: nối backend với workflow, AI extraction và dashboard BQL.
- Kiểm tra nhận tin và phản hồi tự động qua Zalo.

## Đang vướng
- Điện thoại Meo Meo nhận được tin nhưng Deplao chưa ghi nhận sự kiện tin đến.
- Workflow chạy thử thủ công được, chưa chạy tự động khi người dùng nhắn.
- Chưa hoàn tất demo end-to-end bằng tin nhắn thật.

## Workflow mẫu
Nhập `workflows/meo-meo-auto-reply-private.json` vào Deplao, chọn tài khoản và trợ lý Gemini, lưu và bật workflow. Tắt workflow cũ để tránh phản hồi trùng.

Workflow chỉ nhận tin nhắn văn bản trong chat riêng và bỏ qua tin tự gửi. Cần xử lý lỗi kết nối nhận tin trước khi xác nhận demo hoạt động. Chưa tích hợp lưu tin bán, tìm kiếm hay duyệt tin.

## Công nghệ
- Deplao: kết nối tài khoản Zalo và chạy workflow.
- Gemini: tạo câu trả lời.
- Dashboard, lưu trữ và tìm kiếm: dự kiến phát triển sau.

## Nguồn tham khảo
- [Deplao Builder](https://github.com/babyvibe/deplao-builder)

Repo gồm backend local, kiểm thử, tài liệu tiến độ và cấu hình mẫu; không chứa API key thật, cookie hoặc dữ liệu hội thoại thật.
