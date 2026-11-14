# Đăng tin đã duyệt lên Cư Dân Demo

## Trạng thái
Backend/outbox và workflow mẫu đã triển khai, kiểm tra bằng API và giao diện với dữ liệu tổng hợp. Chưa tự import/bật workflow trong Deplao và chưa xác nhận bài thật xuất hiện trong nhóm. Group settings/keys chỉ lưu private trên máy.

## Cách bật
1. Giữ backend local và Deplao mở. Meo Meo phải là thành viên có quyền gửi trong nhóm đã chọn.
2. Nhập `private/group-publisher-workflow.json` vào Deplao.
3. Chọn tài khoản Meo Meo cho workflow `Meo Meo - Publish Approved to Group`, lưu và bật.
4. Giữ workflow chat backend hiện tại hoạt động. Đây là hai workflow khác nhau: chat riêng và lịch đăng nhóm, không thay thế nhau. Không bật lại chatbot Gemini cũ song song với chat backend.
5. Tạo/xác nhận một tin bán rồi BQL duyệt trên dashboard. Tin mới duyệt sẽ tự vào hàng chờ.
6. Tin đã duyệt từ trước khi bật chức năng: bấm `Đưa tin vào hàng chờ đăng nhóm` trên đúng tin đó. Không tự đăng hàng loạt lịch sử.

Mỗi 20 giây workflow lấy tối đa một phần cần gửi. Bài đăng và mã riêng là hai phần; thường cần tới 40 giây cho cả hai. Reload dashboard để thấy trạng thái. Không dùng nút chạy thử làm bằng chứng gửi thật (một số chế độ Deplao mô phỏng node).

## Bài đăng
```text
🛍 TIN ĐÃ ĐƯỢC BQL DUYỆT
Ghế làm việc
Giá: 500,000đ
Tình trạng: Đã dùng 6 tháng

🔖 MÃ MÓN ĐỒ
━━━━━━━━━━━━━━━━
NM-XXXXXXXXXXXX
━━━━━━━━━━━━━━━━
```
Một tin riêng chỉ chứa `NM-XXXXXXXXXXXX` được gửi sau bài đăng để cư dân sao chép chính xác. Node Deplao hiện gửi text, không phải tô màu/bôi đậm hoặc nút clipboard Zalo.

Cư dân nhắn riêng mã cho Meo Meo hoặc `xem NM-...` để kiểm tra tin đang bán. API chỉ trả tin cùng khu đã approved, không trả seller_id. Workflow chat riêng hiện vẫn theo phạm vi người thử đã cấu hình; muốn mở cho cư dân khác cần chủ động mở rộng/xác minh người dùng ở chặng sau.

## Chống đăng trùng và xử lý lỗi
- Approve và enqueue cùng transaction; mỗi tin/nhóm chỉ có một job bài đăng và một job mã.
- Claim khóa một job đang gửi cho nhóm; job tiếp không được gửi trước khi có receipt.
- Chỉ ack bằng token job hiện tại và ID tin Zalo hợp lệ. Không coi HTTP node thành công là tin đã được gửi.
- Sau 180 giây không có ack, lần poll tiếp chuyển sang `Cần kiểm tra nhóm`. Không tự retry vì có thể tin đã gửi nhưng mất ack.
- BQL kiểm tra nhóm rồi mới bấm `Đăng lại sau khi kiểm tra nhóm`. Chỉ phần chưa được xác nhận mới thử lại. Không bảo đảm exactly-once với Zalo; khi uncertain có thể trùng nếu BQL chọn đăng lại phần đã gửi.
- SĐT/email phổ biến trong title/condition được lọc khỏi bài nhóm và chi tiết lookup bằng mã. Đây không thay thế việc BQL kiểm tra quyền riêng tư trước duyệt.
- Tin bán xong khi còn queued không đăng nữa. Tin đã lên nhóm không tự xóa/sửa ở phiên bản này; người mua phải hỏi bot theo mã để kiểm tra còn bán.

## Tệp và cấu hình
`tools/build_group_workflow.py --group-id ID --group-name TEN_NHOM` tạo `private/group-settings.json` và `private/group-publisher-workflow.json`.

Workflow chứa bridge key thật nên không chia sẻ hoặc upload GitHub. Muốn đổi nhóm, tắt publisher, kiểm tra hàng chờ đang gửi, tạo lại settings và restart backend; không đổi đích trong lúc đang gửi.

Backend vẫn chạy localhost. Deplao và backend phải trên cùng máy trong bản này. Tắt máy hoặc đóng Deplao sẽ dừng tự đăng.
