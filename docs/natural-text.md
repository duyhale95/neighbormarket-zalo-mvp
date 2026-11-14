# Đăng bán bằng câu tự nhiên

## Cách thử trên Zalo
Giữ workflow backend đang chạy; không cần nhập workflow mới hoặc bật thêm chatbot Gemini song song.

1. Nhắn `Mình muốn thanh lý ghế làm việc 500k.`
2. Bot hỏi tình trạng. Trả lời `Ghế đã dùng 6 tháng, không hư hỏng.`
3. Bot trả bản nháp có mã tin, giá và tình trạng.
4. Kiểm tra nội dung, rồi nhắn `xacnhan NM-...` với mã thật. Nếu sai, bổ sung/sửa trước khi xác nhận, ví dụ `Đổi giá thành 450k`.
5. BQL duyệt trên dashboard như trước.
6. Tìm bằng `tim ghế`, báo đã bán bằng `daban NM-...`.

Mỗi người/khu có một bản nháp hội thoại đang mở. Đổi món: nhắn `huy nhap` rồi gửi thông tin mới. Bản thiếu thông tin chỉ nằm trong ngữ cảnh hội thoại; dashboard nhận tin draft khi đủ tên, giá và tình trạng. Chỉ sau xác nhận mới pending.

Các lệnh cũ có dấu `|` vẫn dùng được. Tạo tin bằng lệnh cũ sẽ kết thúc ngữ cảnh AI đang mở; bản draft hoàn chỉnh cũ vẫn là một tin riêng nếu chưa hủy.

## Cấu hình local
`run-local.ps1` đọc `private/gemini-settings.json` chứa tên model và `private/gemini-key.xml` là SecureString DPAPI đã mã hóa cho Windows user hiện tại. Hai tệp này không được commit. Key chỉ được giải mã trong bộ nhớ khi chạy backend; không gửi key vào chat.

Cũng có thể cấu hình bằng `GEMINI_API_KEY` và `GEMINI_MODEL` trong môi trường. Nếu không có key/model, luồng lệnh cũ vẫn chạy và `/health` báo `natural_text_enabled=false`.

Gemini xử lý text qua cloud, cần Internet. Backend quản lý dữ liệu/trạng thái; model không có quyền duyệt hoặc gửi tin Zalo. Không gọi model trong transaction ghi SQLite. Event hoàn tất được cache để retry không tạo thêm tin; các request cùng người gửi khi đang chờ sẽ được yêu cầu đợi.

Provider có deadline 10 giây; tác vụ model trả muộn bị bỏ qua. Luồng natural dùng SQLite lock timeout ngắn và kiểm tra deadline trước commit. Workflow Deplao hiện dùng HTTP timeout 15 giây. Nếu AI lỗi/quá thời gian, bot hướng dẫn thử lại hoặc dùng lệnh cũ.

## Kiểm thử
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/check_ui.py
.\.venv\Scripts\python.exe tools/check_gemini_text.py --key-file private/gemini-key.xml --model TEN_MODEL_DANG_CAU_HINH
```
Smoke Gemini dùng dữ liệu tổng hợp và database tạm, không gửi Zalo. Kiểm tra thật qua Zalo do người dùng thực hiện.

## Giới hạn
Chỉ text. Chưa đọc ảnh, natural-language search, semantic search hay tự động kiểm duyệt. Tin do AI trích xuất vẫn cần người bán kiểm tra và BQL duyệt. Bộ test ảnh cũ trong docs/planned-tests vẫn là kế hoạch.

## Tài liệu API tham khảo
- [Gemini generateContent](https://ai.google.dev/api/generate-content)
- [Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
