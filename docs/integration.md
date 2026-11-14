# Hợp đồng tích hợp Deplao → backend

## Trạng thái
Đã kiểm thử backend độc lập. Chưa cấu hình workflow gọi HTTP và chưa xác nhận tin thật Zalo tới backend. Workflow Gemini cũ vẫn là chatbot độc lập, chưa lưu/tìm tin bằng backend này.

## API nhận sự kiện
`POST /events`, header `X-API-Key` bằng bridge key, JSON:

```json
{
  "event_id": "zalo-message-id-stable",
  "community_id": "demo",
  "sender_id": "sender-identifier",
  "text": "ban Ghế | 500000 | đã dùng 6 tháng",
  "thread_type": "private",
  "is_self": false
}
```

- `event_id` lấy ID tin nhắn thật, giữ nguyên khi retry. Cache theo khu/người gửi/ID.
- Sender phải lấy từ metadata Zalo, không lấy từ nội dung chat. Community phải được backend/bridge ánh xạ từ tư cách cư dân đã xác minh, không cho người dùng tự đặt. Demo local cho phép bridge tin cậy khai báo trực tiếp.
- Backend trả `reply`; bridge gửi đúng một lần tới hộp thoại gốc. Không gửi nếu `ignored=true` hoặc reply rỗng.
- Kết quả xử lý là idempotent, nhưng gửi Zalo chưa có outbox: bridge vẫn cần chống gửi reply trùng và xử lý retry trước khi vận hành thật.
- HTTP 422: nhập sai/thiếu dữ liệu; 404: không có tin thuộc quyền; 409: sai trạng thái; 401: sai khóa. Chưa có lớp chuyển lỗi API thành câu trả lời trong Zalo.
- Chỉ gọi local để thử nghiệm. Nếu chạy khác máy cần HTTPS và cấu hình mạng có kiểm soát. Không hardcode khóa vào workflow xuất GitHub.

## Các lệnh thử nghiệp vụ
1. `ban Ghế | 500000 | đã dùng 6 tháng` → draft và mã tin.
2. `xacnhan NM-...` → pending.
3. BQL GET `/listings?community_id=demo` với admin key.
4. BQL POST `/listings/NM-.../review` với admin key, body `{"community_id":"demo","action":"approve","reason":"Đã kiểm tra"}`. Dùng `reject` để từ chối.
5. Người mua `tim ghe` → tối đa 5 tin approved cùng khu, không có seller ID.
6. Chủ tin `daban NM-...` → sold, không còn trong tìm kiếm.

## Cần hoàn thiện trước khi thử với cư dân
- Xác minh kết nối nhận sự kiện Deplao và đúng schema node HTTP theo phiên bản đang cài.
- Định danh cư dân và phân quyền BQL bằng đăng nhập, thay admin key dùng chung.
- Xác nhận người bán nhiều lượt, sửa/hủy/hết hạn tin, bảo vệ liên hệ.
- AI extraction + moderation có người duyệt và ảnh lưu an toàn.
- Tìm kiếm vector, giới hạn tần suất, outbox, log tối thiểu/retention và backup.
