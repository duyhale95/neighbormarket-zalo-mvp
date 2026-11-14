# Sold sync rồi kiểm tra ảnh — plan

1. Sold sync dùng outbox hiện có gửi thông báo ĐÃ BÁN kèm mã trong cùng nhóm; Deplao có node thu hồi nhưng chưa được nghiệm thu, chưa giả định sửa/xóa bài sẽ thành công. Chưa bật thao tác thu hồi. Giữ lịch publisher hiện có.
2. Ảnh: nhận bytes có giới hạn/kiểm tra định dạng, Gemini đọc và đối chiếu mô tả; lưu cờ và ảnh private để BQL xem. Không tuyên bố xác thực quyền sở hữu hay ảnh thật.
3. TDD, test quyền/khu/idempotency, review, backup/restart và push PR #1. Không gửi test ra nhóm bằng công cụ; người dùng nghiệm thu thật.

## Tiêu chí
- Chỉ chủ tin được báo đã bán; lệnh trần khi nhiều món phải hỏi chọn, không tự chọn sai.
- Tin chưa từng lên nhóm và còn queued bị hủy đăng, không tạo thông báo đã bán thừa.
- Tin đã/maybe gửi lên nhóm có đúng một outbox sold; không auto retry uncertain.
- Ảnh giới hạn4MiB/16MP, không fetch URL tùy ý. Mọi nội dung nghi ngờ đi BQL, không autoapprove.
- Tích hợp ảnh vào Deplao chỉ khi adapter tải ảnh từ nguồn kiểm soát được và gửi bytes an toàn. Nếu chưa thể, bàn giao đường upload local hoạt động và ghi rõ giới hạn.

## Triển khai và kiểm chứng
- Sold notification dùng publisher cũ; không cần đổi workflow nhóm.
- Image safety module, photo workflow, DPAPI setup, UI private image view và version-bound manual review đã triển khai.
- 45 tests + browser UI smoke pass. Review phát hiện snapshot race, đã sửa/read transaction và có regression.
- OpenAI API thật với key mới người dùng lưu bằng script: synthetic image clear; không dùng key dán trong chat.
- Chưa xác nhận tin sold/ảnh thật trong nhóm/Zalo; cần người dùng nhập workflow ảnh và thử.
