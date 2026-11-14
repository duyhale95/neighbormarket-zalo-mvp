# Tiến độ local 14/11/2026

## Đã thực hiện
- Tạo venv riêng, cài runtime dependencies và công cụ browser QA.
- Backend localhost, database/private keys không commit.
- Cầu nối Deplao text: metadata headers, raw body prefix, lỗi nghiệp vụ trả reply rõ ràng.
- Dashboard BQL: lọc, duyệt/từ chối có lý do, sao chép tin đã duyệt, khóa trang và chống phản hồi cũ hiện lại dữ liệu.
- Script xuất workflow local chỉ cho người thử được xác nhận; tệp có bridge key nằm trong private, chưa import/bật trong Deplao.
- 10 unittest đạt. Browser headless Edge đạt vòng duyệt, chống HTML injection, mobile width, regression tải chậm sau khóa.
- Review lần đầu phát hiện 2 lỗi; có regression fail → fix → pass cho cả hai.

## Cần người dùng thao tác
- Import `private/deplao-local-workflow.json`, chọn Meo Meo, tắt workflow Gemini cũ rồi bật workflow backend.
- Nhắn tin thật từ Thiên Bảo để xác minh nhận/gửi. Không dùng nút chạy thử làm bằng chứng Zalo thật.
- Mở dashboard và nhập admin_key local để duyệt tin; không gửi key vào chat.

## Chưa thực hiện
- Hội thoại tự nhiên Gemini, ảnh, semantic search và kết nối người mua–bán.
- Supabase/pgvector, định danh cư dân thật, login BQL production, deploy VPS.
- Chưa xác nhận vòng Zalo thật của workflow backend mới.

Kế hoạch dài hạn ở `docs/superpowers/plans/2026-11-14-local-mvp-approval.md`. Tài liệu kế hoạch không phải bằng chứng tính năng đã hoàn tất.
