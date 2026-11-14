# Đã bán và kiểm duyệt an toàn ảnh

## 1. Đồng bộ đã bán
- Chủ tin nhắn `daban NM-...` hoặc `đã bán`. Nếu có nhiều món đang bán, bot hỏi chọn mã, không tự chọn một món.
- Backend loại món khỏi tìm kiếm và lookup mã ngay.
- Nếu bài đã lên nhóm (hoặc đang gửi/chưa rõ kết quả), outbox gửi một thông báo **ĐÃ BÁN** kèm mã qua workflow đăng nhóm hiện có.
- Tin vẫn queued chưa từng gửi được hủy đăng, không tạo thông báo thừa.
- Không sửa/thu hồi bài cũ ở phiên bản này. Deplao có node thu hồi nhưng chưa nghiệm thu quyền/hạn chế thời gian và receipt cần thiết; không giả định việc xóa sẽ thành công.
- Nếu mất ack, BQL kiểm tra nhóm rồi mới dùng nút gửi lại trên dashboard. Không auto retry trạng thái uncertain.

## 2. Kiểm duyệt ảnh
Mục tiêu đợt này là nội dung an toàn, không phải xác thực ảnh thật, quyền sở hữu, hàng cấm đầy đủ hay tìm ảnh trùng. Dùng [OpenAI Moderation API](https://developers.openai.com/api/docs/guides/moderation) với `omni-moderation-latest`, gửi ảnh và nội dung mô tả cùng nhau. Không dùng model chat để tự phán quyết xuất bản.

Ảnh được chuẩn hóa JPEG, bỏ EXIF, tối đa 1600px chiều dài. Đầu vào PNG/JPEG/WebP tối đa4MiB,16triệu pixel; tối đa5ảnh/tin. Dữ liệu nằm trong SQLite private. Ảnh có thể gửi kèm bài bằng publisher v2; xem [hướng dẫn đăng ảnh](group-photos.md).

### Bật khóa an toàn
Không gửi key vào chat. Thu hồi khóa đã từng lộ, tạo khóa mới ở trang quản lý OpenAI, chạy:
```powershell
pwsh -File .\setup-moderation.ps1
```
Nhập key vào ô ẩn. Script lưu Windows DPAPI tại `private/moderation-key.xml`. Restart backend để nạp. Không upload private.

Kiểm tra bằng ảnh màu tổng hợp, không dùng ảnh cư dân:
```powershell
.\.venv\Scripts\python.exe tools/check_moderation.py
```

### Nhận ảnh từ Zalo
1. Nhập `private/image-safety-workflow.json` trong Deplao; chọn Meo Meo; lưu/bật.
2. Giữ workflow chat text và workflow lịch đăng nhóm. Ba workflow nhận loại sự kiện khác nhau.
3. Người thử nhắn đầy đủ text, ví dụ `Mình bán ghế 500k, dùng 6 tháng, không hỏng.` Chờ bản nháp.
4. **Trước khi xác nhận**, gửi riêng một ảnh sản phẩm. Workflow ảnh hiện lấy ảnh đầu tiên; gửi từng ảnh một, không dựa vào caption album.
5. Bot nhận ảnh, kiểm tra an toàn và báo kết quả/chuyển BQL kiểm tra. Sau đó người bán nhắn `xác nhận`.
6. BQL tải lại dashboard, xem ảnh, nhãn/cờ rồi duyệt hoặc từ chối.

Adapter chỉ nhận URL HTTPS từ `photo-zalo.zadn.vn` hoặc subdomain `zcdn.me` / `photo-stal-N.zdn.vn`; không follow redirect; DNS phải toàn IP global và kết nối ghim IP đã kiểm tra với TLS host gốc. Có timeout và giới hạn tải. URL/host không hỗ trợ sẽ báo lỗi thay vì truy cập tùy ý. CDN trả403/404/408/429/5xx được thử tối đa3lần trong deadline8giây. Nếu ảnh không vào, xem HTTPstatus/host trong log và giữ kiểm tra IP/TLS; không mở allowlist tùy tiện.

### Upload trực tiếp khi thử local
Trên dashboard, ở tin draft/pending chọn ảnh rồi bấm **Tải ảnh và kiểm tra an toàn**. Có nút **Xem ảnh** và **Kiểm tra ảnh lại**. URL ảnh cần admin key trong header, không public hoặc nhúng key vào URL.

### Cách xử lý kết quả
- `clear`: chưa phát hiện nội dung mất an toàn theo model; vẫn cần BQL duyệt tin.
- `flagged`: hiển thị nhãn cho BQL; không tự coi người bán lừa đảo.
- `unavailable`/`error`: không coi là an toàn; cần cấu hình/kiểm tra lại hoặc BQL xác nhận kiểm tra thủ công.
- `pending`: chặn duyệt trong khi đang kiểm tra. Nếu process dừng, sau60giây có thể kiểm tra lại.
- `stale`: mô tả thay đổi sau kiểm duyệt; kiểm tra lại với nội dung mới hoặc BQL xem thủ công.
- Manual override yêu cầu checkbox và lý do, có ghi audit; ảnh/nội dung và token duyệt phải cùng phiên bản. Có ảnh mới/đổi nội dung sau khi tải dashboard thì phải tải lại và xem phiên bản mới.

Chỉ thêm/kiểm tra lại ảnh trước khi tin approved. Không cho thay ảnh âm thầm sau khi đã đăng.

## Trạng thái kiểm chứng
- Unit/integration: dữ liệu ảnh hợp lệ/sai, scope/quyền, duplicate, SSRF/DNS, stale content, snapshot override và outbox sold.
- UI: upload ảnh, fetch private, chặn duyệt khi chưa xem thủ công, duyệt sau xác nhận, desktop/mobile.
- Dịch vụ OpenAI thật: ảnh màu tổng hợp đã trả clear bằng key local; không sử dụng khóa đã dán trong chat.
- Chưa nghiệm thu ảnh thật qua workflow Zalo mới hoặc thông báo sold trên nhóm bằng công cụ. Người dùng thực hiện vòng kiểm tra thật.
