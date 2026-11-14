# Quy chuẩn tin nhắn tự động

- Plain text để đọc rõ trên Zalo; không dùng Markdown giả bôi đậm.
- Một tiêu đề, dòng trống phân nhóm, từng trường trên một dòng, mã ở dòng riêng.
- Giá nguyên VND dạng `500.000 đ`; giá0 vẫn là `0 đ`. Không tự điền trường chưa biết.
- Bản nháp đầy đủ: tên món/giá/tình trạng/trạng thái/mã và cách xác nhận/hủy.
- Bản nháp thiếu: hiển thị dữ liệu đã biết, mục thiếu ghi Chưa cung cấp, hỏi một trường tiếp theo.
- Tìm mua: mỗi món là một khối đánh số, đủ tên/giá/tình trạng/mã. Giới hạn độ dài bằng số khối, không cắt mất trường giữa chừng.
- Xem mã: thông tin món và trạng thái; không thêm thương hiệu/nguồn/giá gợi ý chưa có dữ liệu.
- Ảnh: phân biệt đã lưu, kiểm duyệt tự động và BQL duyệt. Không đồng nhất an toàn nội dung với xác thực ảnh thật.
- Lỗi: tiêu đề và lý do có hướng dẫn, không gửi traceback hay secret.
- Bài nhóm và thông báo đã bán cũng dùng cùng định dạng; tin chỉ chứa mã riêng giữ nguyên để dễ copy.
- Không sửa tin đã gửi hoặc thay thế cache event cũ. Mẫu áp dụng cho phản hồi sự kiện mới và bài nhóm chưa gửi.

Mẫu nằm ở `backend/messages.py`. 52 tests và UI smoke đạt sau khi tích hợp.
