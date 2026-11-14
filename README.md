# NeighborMarket Zalo MVP

Trợ lý chợ cư dân hoạt động qua chat riêng Zalo; quản trị qua dashboard.

## Đã làm
- Chốt hướng MVP trên Zalo cá nhân, sử dụng Deplao và Gemini.
- Tạo trợ lý Meo Meo và workflow nhận tin → Gemini → trả lời.
- Chạy thử thủ công workflow thành công.
- Chuẩn bị workflow trả lời tin nhắn văn bản riêng, không cần lệnh /chat.

## Đang làm
- Viết project brief và PRD cho MVP.
- Thiết kế UI flow cho người mua, người bán và Ban Quản lý.
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

Repo gồm tài liệu tiến độ và cấu hình mẫu; không chứa API key, cookie hoặc dữ liệu hội thoại.
