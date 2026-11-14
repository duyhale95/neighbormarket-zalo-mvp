# Brief và PRD — bản MVP 0.1

## Bài toán và người dùng
Cư dân khó tìm tin bán còn hiệu lực trong nhóm chat. Người bán cần đăng tin nhanh; người mua cần tìm đúng món; BQL cần kiểm soát tin trước khi công khai.

## Phạm vi
- Chat riêng Meo Meo: đăng bán, xác nhận, tìm mua, báo đã bán.
- Nhóm chợ: chỉ trưởng/phó đăng tin đã duyệt; đăng thủ công ở MVP.
- BQL: danh sách chờ duyệt, duyệt/từ chối bằng API trước; dashboard sau.
- AI dự kiến: trích xuất ảnh/text, phân loại/kiểm duyệt, tìm kiếm vector.
- Backend chịu trách nhiệm quyền, trạng thái, dữ liệu và chống xử lý trùng.

## Tiêu chí nghiệm thu
1. Người bán tạo nháp, xác nhận thành tin chờ duyệt.
2. Chỉ BQL được duyệt/từ chối; kết quả quyết định được ghi lại.
3. Tìm mua chỉ trả tin đã duyệt còn bán, thuộc cùng khu.
4. Chỉ chủ tin được báo đã bán; tin đó biến mất khỏi tìm kiếm.
5. Tin nhắn gửi lại cùng ID không tạo thêm tin hoặc thao tác.
6. Không đưa khóa API, phiên Zalo, dữ liệu thật lên GitHub.

## Giới hạn phiên bản hiện tại
Backend demo nhận sự kiện chuẩn hóa, không trực tiếp đăng nhập Zalo. Luồng text dùng lệnh xác định để kiểm chứng nghiệp vụ, không giả là AI. SQLite và tìm kiếm từ khóa dùng cho chạy local. Chưa có Supabase, pgvector, OCR/ảnh, đăng nhập BQL theo cá nhân hoặc triển khai VPS. API key cho BQL chỉ dùng thử local, không thay thế đăng nhập production.

## UI flow
Người bán: chat riêng → bản nháp → xác nhận → chờ BQL → đang bán → đã bán.

Người mua: chat riêng → nhập nhu cầu → danh sách tin → xem mã tin. Kết nối người bán và bảo vệ liên hệ là chặng sau; API tìm kiếm không trả ID người bán.

BQL: đăng nhập (chặng sau) → hàng đợi → xem nội dung → duyệt/từ chối kèm lý do → sao chép tin đăng nhóm.

## Quyết định còn cần mentor
- Chọn kênh Zalo tích hợp phù hợp trước khi vận hành thực tế; listener Deplao hiện chưa nhận được tin thật.
- Định danh cư dân bằng lời mời/xác minh BQL; không tin khu/hộ do người dùng tự khai.
- Nghiệm thu bằng vòng đăng bán–duyệt–tìm mua, không chỉ chatbot trả lời.
