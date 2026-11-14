# NeighborMarket Zalo MVP

Trợ lý chợ cư dân qua Zalo cá nhân, kết nối bằng Deplao và backend FastAPI chạy local. Cư dân chat riêng với Meo Meo; BQL duyệt trên dashboard; publisher đăng tin vào nhóm.

## Chức năng hiện có

- Đăng bán bằng câu tự nhiên với Gemini, hỏi thông tin thiếu, giữ bản nháp nhiều lượt.
- Xác nhận bằng `xác nhận`; hủy bằng `hủy nháp`.
- Nhận ảnh Zalo hoặc upload local; chuẩn hóa ảnh, kiểm duyệt an toàn OpenAI, lưu private.
- BQL xem ảnh, duyệt/từ chối có lý do; ảnh/nội dung phải đúng phiên bản được xem.
- Tìm từ khóa hoặc xem theo mã; chỉ trả tin cùng khu đã duyệt, còn bán.
- Publisher v2 gửi ảnh đầu kèm nội dung, ảnh bổ sung và mã riêng; bổ sung ảnh cho bài cũ.
- Chủ tin báo đã bán; loại khỏi tìm kiếm, đưa thông báo ĐÃ BÁN vào nhóm.
- Chống xử lý trùng, kiểm tra chủ tin/khu, outbox và receipt từng phần. Trạng thái gửi chưa rõ cần người kiểm tra trước khi đăng lại.

## Chạy local

Yêu cầu Python 3.11+, PowerShell 7 và Deplao trên cùng máy để đọc ảnh local.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
pwsh -File .\run-local.ps1
```

- Dashboard: http://127.0.0.1:8000/admin
- API thử: http://127.0.0.1:8000/docs
- Trạng thái: http://127.0.0.1:8000/health

Script tạo `private/local-config.json` với bridge key và admin key khác nhau. Nhập admin key vào dashboard. Database, ảnh, khóa DPAPI, workflow chứa key và backup ở `private/`, không được commit/chia sẻ công khai. Gemini/OpenAI vẫn cần Internet dù backend chạy local.

Đọc [cấu hình local và Deplao](docs/local-setup.md) để nạp model/key và sinh ba workflow hiện tại.

## Ví dụ

```text
Mình muốn bán ghế làm việc 500k, dùng 6 tháng, không hỏng.
```

Gửi ảnh trước khi xác nhận, xem nháp rồi nhắn `xác nhận`. BQL duyệt trên web. Người mua nhắn `tìm ghế` hoặc gửi mã `NM-...`. Chủ tin báo bán xong bằng `đã bán MÃ_TIN`.

Ba workflow: chat riêng, nhận ảnh, đăng nhóm có ảnh v2. Chỉ bật một publisher nhóm; chọn đúng tài khoản Zalo và kiểm tra bộ lọc người gửi trước khi thử bằng tài khoản khác.

## Hướng dẫn

- [Cài đặt, cấu hình và API bridge](docs/local-setup.md)
- [Hội thoại đăng bán](docs/natural-text.md)
- [Đã bán và kiểm duyệt an toàn ảnh](docs/sold-and-image-safety.md)
- [Đăng nhóm có ảnh — publisher v2](docs/group-photos.md)
- [Quy chuẩn tin nhắn](docs/message-style.md)
- [Roadmap ưu tiên trải nghiệm cư dân](docs/roadmap.md)

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Browser QA dùng database tạm và dữ liệu tổng hợp:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tools/check_ui.py
```

Script UI dùng Edge headless trên Windows. CI chạy unittest, không cần key/Zalo. `check_gemini_text.py` và `check_moderation.py` là smoke test cloud tùy chọn bằng dữ liệu tổng hợp.

## Giới hạn

Đây là MVP local. BQL dùng admin key demo; cư dân/khu cần xác minh trước khi mở rộng. Tìm kiếm hiện là từ khóa; chưa có semantic search, gợi ý giá, tìm ảnh trùng, đối chiếu ảnh/mô tả hoặc kết nối hai bên đầy đủ. Moderation không xác thực ảnh thật/quyền sở hữu. Báo đã bán chưa tự thu hồi bài cũ. Máy và Deplao phải tiếp tục chạy để nhận/gửi tin.

## Nguồn tham khảo

[Deplao Builder](https://github.com/babyvibe/deplao-builder)
