# Cư Dân Demo — plan đăng nhóm

**Đích đã được người dùng chọn:** nhóm Cư Dân Demo của tài khoản Meo Meo, ID đã đối chiếu contacts local. Group ID/name và keys chỉ ở private/config, không hardcode trong source public.

**Flow:** approve → atomic outbox (bài đăng + mã riêng) → Deplao poll 20 giây → claim một phần → gửi nhóm → ack bằng Zalo msgId. Hai phần có trạng thái riêng; không gửi mã nếu bài đăng chưa ack.

**Hiển thị:** khung ký tự/nhãn rõ cho mã trong bài đăng; thêm một tin chỉ có mã để cư dân sao chép. Không hứa có nút clipboard/tô màu trong Zalo vì node sendMessage hiện chỉ gửi text.

## Tasks
- [x] Tests fail trước code: chỉ approved/cùng khu được enqueue; approve lại không nhân đôi; một claim tại một thời điểm; ack token/id; code sau post; lease hết hạn không tự đăng lại; sold không đăng; quyền riêng.
- [x] Module publishing.py + API claim/ack/retry/queue, danh sách trạng thái trên dashboard.
- [x] Sinh workflow schedule riêng, giữ workflow chat hiện có; cấu hình private theo nhóm đã xác nhận.
- [ ] Review và test/UI; backup/restart local; cập nhật GitHub.
- [ ] Nhập workflow vào Deplao, chọn Meo Meo và kiểm chứng tin thật. Nếu cần người dùng thao tác thì nêu chính xác, không giả đã đăng.

## Ràng buộc
- Chỉ lưu tin vào hàng chờ khi được BQL duyệt. Tin đã approved trước lúc bật tính năng có nút đưa vào hàng chờ riêng.
- Backend không tự đăng nhập Zalo, không mở listener mới. Chỉ Deplao gửi.
- Khi timeout/không nhận ack: trạng thái uncertain, cần BQL kiểm tra nhóm trước khi chọn đăng lại. Không tuyên bố exactly-once với dịch vụ ngoài.
- Không post seller_id hoặc liên hệ. Text công khai lọc SĐT/email phổ biến; vẫn cần BQL kiểm tra nội dung trước duyệt.
- Sold sau khi đã đăng không tự xóa/sửa bài cũ trong đợt này; tìm kiếm trong bot vẫn loại tin sold.

## Kiểm tra
- 32 tests local pass; UI smoke mô phỏng claim/ack cho hai phần và kiểm tra trạng thái queued/posted.
- Review độc lập: không phát hiện lỗi critical/important. Chưa gửi Zalo thật cho chức năng đăng nhóm.
