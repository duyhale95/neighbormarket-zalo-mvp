# Bắt đầu local — bản backend + Deplao text

Cập nhật: Gemini text tự nhiên đã được bổ sung; xem [hướng dẫn mới](natural-text.md). Phần dưới mô tả luồng lệnh xác định vẫn được hỗ trợ.

## Đã có trong phiên bản này
Backend lưu SQLite, dashboard `/admin`, endpoint text `/bridge/zalo`, script xuất workflow riêng tư cho người thử đã xác nhận. Chưa tích hợp AI extraction/ảnh; workflow này dùng lệnh xác định để nghiệm thu đường truyền và nghiệp vụ. Workflow Gemini cũ là một luồng khác, không tự lưu dữ liệu vào đây.

## Chạy
```powershell
cd D:\Downloads\FOLDER\neighbormarket-zalo-mvp
pwsh -File .\run-local.ps1
```
Backend giữ cửa sổ chạy; Ctrl+C để dừng. Dữ liệu nằm ở `private/market.db`, keys ở `private/local-config.json`. Không xóa private nếu muốn giữ dữ liệu.

Mở http://127.0.0.1:8000/admin, nhập `admin_key` từ file local-config.json và khu `demo`. Không gửi file/key lên chat hoặc GitHub. Đây là bảng quản trị dùng key local, chưa phải login BQL production.

## Xuất workflow
```powershell
.\.venv\Scripts\python.exe tools/build_local_workflow.py --sender-id ID_NGUOI_THU
```
Tệp xuất `private/deplao-local-workflow.json` có bridge key thật nên chỉ giữ ở máy này. Script không đổi cấu hình Deplao và không tự gửi Zalo.

Trong Deplao:
1. Nhập tệp workflow local, chọn tài khoản Meo Meo.
2. Kiểm tra trigger chỉ nhận chat riêng từ tài khoản thử, bỏ qua tin tự gửi.
3. Tắt workflow Gemini trả lời cũ, lưu và bật workflow backend mới.
4. Không bật cả hai workflow. Để quay lại chatbot cũ: tắt workflow backend rồi bật lại workflow Gemini.

Workflow `MarketBackend` gửi text/plain kèm prefix cố định để Deplao không cố parse nội dung cư dân thành JSON. Backend bỏ prefix và xử lý text gốc. Sender/msg ID nằm trong headers, khu `demo` do server quyết định. Node IF chỉ gửi reply khi HTTP status=200. Đã đối chiếu source Deplao; vẫn cần nghiệm thu bằng tin nhắn thật trên bản cài đặt.

## Kịch bản thực hành
1. Thiên Bảo nhắn Meo Meo: `ban Ghế làm việc | 500000 | Đã dùng 6 tháng`.
2. Bot trả bản nháp và mã `NM-...`.
3. Nhắn `xacnhan NM-...` (thay mã thật).
4. Trên dashboard bấm tải danh sách, nhập lý do và duyệt.
5. Nhắn `tim ghế`: thấy mã và giá.
6. Nhắn `daban NM-...`: đánh dấu đã bán.
7. Nhắn `tim ghế`: tin đó không còn xuất hiện.

Chưa có kết nối người mua–bán, vector search hoặc tự đăng nhóm. Dashboard sao chép nội dung để BQL tự đăng nhóm.

## Kiểm tra
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
Test AI dự kiến chưa có implementation được giữ ở `docs/planned-tests/test_ai.py`, chưa thuộc bộ test chạy của phiên bản này. Các chặng AI/ảnh/hội thoại tự nhiên trong kế hoạch chưa được coi là hoàn tất.
