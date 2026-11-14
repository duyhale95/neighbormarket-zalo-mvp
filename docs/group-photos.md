# Đăng ảnh món hàng vào nhóm — publisher v2

## Kết quả
- Có ảnh: ảnh đầu tiên đi kèm nội dung bài, các ảnh khác gửi tiếp, cuối cùng là mã riêng để sao chép.
- Không có ảnh: bài văn bản và mã như trước.
- Chỉ lấy ảnh đã lưu thuộc đúng tin đã được BQL duyệt. Không dùng URL ảnh cũ từ CDN và không công khai endpoint ảnh admin.
- File JPEG được xuất vào private/group-media theo ID ảnh, Deplao đọc file local. Backend và Deplao cần chạy cùng máy trong bản này.

## Cập nhật Deplao
1. Tắt **workflow đăng nhóm cũ**; không tắt workflow chat riêng hoặc nhận ảnh.
2. Nhập `private/group-publisher-workflow-v2.json`.
3. Chọn Meo Meo, lưu và bật `Meo Meo - Publish Approved with Photos v2`.
4. Duyệt một tin mới có ảnh rồi kiểm tra nhóm. Mỗi20giây gửi một phần; nhiều ảnh cần nhiều lượt hơn.

Tin đã đăng chỉ chữ từ trước: trên dashboard bấm **Đăng bổ sung ảnh món này**. Hệ thống chỉ bổ sung ảnh chưa được xếp lịch, không đăng lại nội dung hoặc mã đã gửi thành công.

Backend không cho workflow v1 nhận job có ảnh, tránh gửi bài thiếu ảnh. Đã reconcile job đang queued từ phiên bản cũ. Nếu ảnh gửi lỗi/mất ack, trạng thái uncertain và cần kiểm tra nhóm trước khi đăng lại; phần đã ack không gửi lại.

## Nghiệm thu
- 57 unit/integration tests pass; browser UI smoke pass.
- Đã đối chiếu node zalo.sendImage của source Deplao: filePath + message/caption; receipt từ attachment[0].msgId.
- Test local xác nhận cover caption, nhiều ảnh đúng thứ tự, tương thích tin không ảnh, ảnh bổ sung cho bài cũ và sold hủy ảnh đang chờ.
- Chưa gửi ảnh thật vào nhóm qua workflow v2; người dùng cần nhập/bật và thử. File chứa bridge key nên không chia sẻ hoặc commit.
