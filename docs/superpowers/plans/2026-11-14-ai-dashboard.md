# AI intake and moderation dashboard implementation plan

**Goal:** Đọc text/ảnh, hỏi thông tin thiếu và duyệt bản nháp bằng dashboard local.
**Spec:** Tiếp nối `docs/brief-prd.md`; người dùng chọn local trước, chưa có Supabase/VPS.
**Architecture:** `/ai/events` dùng Gemini generateContent (inline image + JSON schema), lưu bản nháp hội thoại riêng theo khu/người gửi. Chỉ code quyết định chuyển trạng thái. `/events` cũ giữ lệnh xác định. UI local phục vụ cùng FastAPI; admin key và bridge key chỉ giữ trong bộ nhớ trình duyệt.

## Ràng buộc
- Không lấy ảnh từ URL do người dùng gửi: nhận base64, xác minh định dạng, tối đa 4 MiB / 16 triệu pixel; lưu private.
- Không đoán giá hoặc tình trạng từ ảnh. Trường thiếu hỏi lại; người bán xác nhận trước khi gửi BQL.
- Kết quả AI không có quyền duyệt/xuất bản; luôn chờ BQL. Cờ AI là gợi ý, không kết luận lừa đảo.
- Tin trùng không gọi AI lại khi đã có kết quả; không giữ khóa SQLite khi chờ API.
- API key sai, JSON model hỏng, thiếu cấu hình, ảnh sai: báo lỗi có kiểm soát, không để lộ secrets.
- Gemini config qua env hoặc DPAPI file local, không chứa khóa trong repo/workflow.

## Task 1 — AI và hội thoại
- [ ] Viết tests provider HTTP mock và lifecycle AI; quan sát fail trước code.
- [ ] Thêm `backend/ai.py`, `backend/intake.py`; tích hợp vào app factory với provider inject cho tests.
- [ ] Kiểm tra ảnh, dữ liệu model, đa lượt, tenant/owner, duplicate và lỗi provider.

## Task 2 — Dashboard
- [ ] Giao diện danh sách/trạng thái/chi tiết/ảnh, duyệt-từ chối có lý do và sao chép nội dung tin đã duyệt.
- [ ] Trang thử chat local dùng bridge key, text/ảnh; phân biệt rõ chưa phải Zalo.
- [ ] Test HTTP, browser desktop/mobile, nhập nội dung nguy hiểm không thực thi HTML.

## Task 3 — Hướng dẫn và nối Deplao
- [ ] Script chạy AI từ key env hoặc DPAPI; cập nhật README và hợp đồng API.
- [ ] Đối chiếu source Deplao; chỉ xuất workflow nếu truyền JSON an toàn và xử lý lỗi đúng.
- [ ] Smoke Gemini thật bằng dữ liệu tổng hợp khi có key local; không dùng dữ liệu cư dân.
- [ ] Review, test, push vào nhánh PR #1, kiểm tra GitHub.

## Cần thao tác bên ngoài sau đợt này
- Khôi phục listener Meo Meo và thử tin Zalo thật. Không chạy thêm listener cạnh tranh Deplao.
- Ảnh Zalo cần adapter tải từ nguồn được kiểm soát; bản API này không tự tải URL bất kỳ.
- Supabase, pgvector, đăng nhập BQL production, VPS và outbox gửi Zalo chưa nằm trong đợt local.

## Thiết kế dashboard
Màu nền #f2f5f7, trắng #ffffff, chữ #173042, xanh lá #16624f, cảnh báo #a66313. Font Segoe UI có sẵn. Bố cục bàn duyệt tin: cột danh sách trái, hồ sơ và hành động phải; mobile xếp dọc. Không ảnh trang trí, không thư viện CDN. Tập trung trạng thái và quyết định, không dùng số liệu giả.
