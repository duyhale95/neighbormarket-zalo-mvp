# Natural text listing intake — implementation plan

**Goal:** Người bán chat tự nhiên, bổ sung thông tin qua nhiều lượt, xác nhận trước khi BQL duyệt. Giữ workflow Deplao và endpoint hiện tại.
**Architecture:** Gemini chỉ trả patch JSON (sell/other, title, price_vnd, condition). `NaturalIntake` lưu draft riêng theo khu/người gửi, hỏi thiếu bằng code, chỉ tạo listing draft khi đủ. Code xác nhận hiện tại chuyển sang pending. Không gọi model trong transaction SQLite. In-flight guard theo người gửi và kiểm tra revision chống ghi đè ngữ cảnh.
**Tech:** FastAPI/SQLite/httpx/Pydantic hiện có. Key đọc từ env hoặc file DPAPI local; model theo cấu hình đã thử, không hardcode khóa.

## Tasks
- [x] Tests red: provider validation, đa lượt, duplicate, sửa nháp, confirm thiếu, owner/khu, hủy, lỗi AI và cạnh tranh.
- [x] Thêm backend/ai_text.py và backend/natural.py; giữ nguyên các lệnh ban có dấu |, tim, xacnhan, daban.
- [x] Hủy nháp rõ ràng bằng `huy nhap`; không để model tự xác nhận/xuất bản.
- [x] Key/model local, smoke API Gemini bằng dữ liệu tổng hợp; không gửi Zalo tự động.
- [x] Review, kiểm thử, restart backend giữ database/keys và push PR #1.

## Constraints
- Gemini timeout tối đa 10 giây, tổng request giới hạn 11 giây để nằm dưới timeout Deplao 15 giây. Không retry tự động bên trong.
- Chỉ text trong đợt này. Không ảnh, vector search, natural-language buyer search hoặc tự động kiểm duyệt.
- Bản nháp chỉ một món mỗi người/khu; dùng `huy nhap` trước khi đổi món.
- Không in key, không sửa DB Deplao, không đổi cấu hình workflow đang chạy.
- JSON không hợp lệ: báo lỗi có kiểm soát, không tạo tin sai. Event hoàn tất được cache; AI lỗi cho phép gửi lại.

## Validation
- Toàn bộ tests cũ và tests mới; UI smoke giữ dashboard hoạt động.
- Smoke model thật: ghế giá 500k thiếu tình trạng → bổ sung tình trạng → đủ dữ liệu, không auto-confirm.
- Tin thật Zalo do người dùng gửi sau khi backend mới chạy.

## Bằng chứng triển khai
- 22 unittest pass; UI smoke pass.
- Gemini thật qua backend với database tạm: 2 lượt tổng hợp đạt; không gửi Zalo.
- Review độc lập: phát hiện deadline/cancel race, đã có regression fail rồi pass và re-review không còn lỗi important/critical.
- Gemini có thể nhắc lại giá đã biết thay vì null; code chấp nhận giá không đổi, smoke kiểm tra không tự đổi giá.
- Chờ người dùng nghiệm thu natural text trên Zalo thật.
