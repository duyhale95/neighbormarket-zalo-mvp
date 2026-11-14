# NeighborMarket Local MVP — Implementation Plan để duyệt

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans sau khi người dùng duyệt. Không triển khai hoặc tải dependency chỉ vì tài liệu này đã tồn tại.

**Trạng thái:** Đề xuất, chờ người dùng duyệt. Thay thế kế hoạch AI/dashboard chưa thực hiện.

**Goal:** Chạy được trên máy Windows một vòng đăng bán bằng text/ảnh → người bán xác nhận → BQL duyệt → người mua tìm thấy → chủ tin báo đã bán, sau đó nối cùng backend với Zalo qua Deplao.

**Architecture:** FastAPI phục vụ API và dashboard cùng một địa chỉ localhost. Gemini chỉ trích xuất, phân loại và đưa ra gợi ý kiểm duyệt; code quản lý quyền/trạng thái. SQLite và thư mục private lưu dữ liệu thử. Deplao là adapter nhận/gửi Zalo, không phải database hay nơi đặt toàn bộ nghiệp vụ.

**Tech Stack:** Python 3.13 hiện có, FastAPI, SQLite, Pillow, Gemini REST generateContent, HTML/CSS/JavaScript thuần, PowerShell 7. Không thêm n8n, Docker, Node frontend, Supabase hoặc VPS ở đợt này.

**Spec:** `docs/brief-prd.md`, bổ sung phạm vi duyệt trong tài liệu này.

## 1. Hiện trạng đã xác minh

- Repo local: `D:/Downloads/FOLDER/neighbormarket-zalo-mvp`.
- Nhánh `feat/marketplace-backend`, PR #1 trên GitHub; chưa merge main.
- Đã có backend lệnh text xác định, lưu SQLite, duyệt/từ chối, tìm từ khóa, đánh dấu đã bán. 6 bài kiểm tra đã đạt ở chặng trước.
- Zalo trên điện thoại Meo Meo nhận tin; lần kiểm tra trước Deplao chưa phát sự kiện tin đến. Chưa kết luận nguyên nhân cuối cùng.
- `tests/test_ai.py` là bản test viết trước, chưa có `backend/ai.py`; do đó bộ test mở rộng chưa thể pass. Không coi đây là tính năng đã làm xong.
- Chưa có dashboard, AI extraction, ảnh, Supabase, pgvector, BQL login production hoặc VPS.

## 2. Máy có gì, cần tải gì?

Kiểm tra ngày 14/11/2026:

| Công cụ | Hiện có | Quyết định |
|---|---|---|
| Python | 3.13.3 | Giữ nguyên; tạo venv riêng cho repo |
| Git | 2.54.0 | Giữ nguyên |
| PowerShell | 7.6.9 | Dùng chạy script local |
| Node.js | 24.14.0 | Không cần cho backend/UI thuần; không cài lại |
| Deplao | Đã cài | Giữ nguyên, không mở thêm listener cạnh tranh |
| FastAPI / uvicorn / httpx | Đã cài global | Cài lại vào venv theo requirements để tái lập |
| Pillow | 11.1.0 global | Khai báo vào requirements và cài vào venv |
| Playwright | Chưa có Python package | Người thực hiện cài cùng Chromium khi tới bước kiểm thử UI; không bắt bạn cài thủ công trước |
| Gemini key | Có file DPAPI local từ phiên trước | Kiểm tra còn dùng được, không in khóa hoặc gửi vào chat |

**Bạn cần chuẩn bị:** Internet, tài khoản Meo Meo trên điện thoại, tài khoản Thiên Bảo để thử, 3–5 ảnh món đồ không có thông tin riêng tư, tình trạng thật và giá mong muốn. Không cần tạo Supabase hoặc thuê VPS.

**Lưu ý local:** Backend, UI và database nằm trên máy bạn. Gemini vẫn là dịch vụ cloud: text/ảnh sẽ được gửi tới Google khi bạn thử AI. Máy tắt thì dịch vụ dừng. Chưa có chế độ AI offline.

## 3. Luồng và phạm vi sản phẩm

### Người bán
1. Gửi text/ảnh trong chat thử local hoặc chat riêng Zalo khi adapter hoạt động.
2. AI trả dữ liệu cấu trúc: tên món, giá được người dùng nêu, danh mục, mô tả, tình trạng được xác nhận, tag và cờ cần xem xét.
3. Backend hỏi từng thông tin bắt buộc còn thiếu: tên món, giá nguyên VND, tình trạng.
4. Lưu bản nháp theo khu + người gửi, tiếp tục đúng bản nháp khi trả lời.
5. Bot hiển thị bản nháp đầy đủ, người bán xác nhận bằng thao tác/lệnh rõ ràng.
6. Tin chuyển chờ BQL duyệt. Không tự đăng nhóm.
7. Chủ tin có thể đánh dấu đã bán; không cho người khác thực hiện.

### Người mua
1. Nhập nhu cầu tự nhiên hoặc lệnh tìm.
2. AI trích xuất từ khóa và giới hạn giá; backend áp dụng bộ lọc bằng code.
3. Chỉ trả tin cùng khu, đã duyệt, còn bán. Không tự bịa tin, giá hoặc trả ID người bán.
4. Chặng local chỉ xem kết quả/mã tin. Kết nối người mua–bán, chat relay ẩn danh và xử lý giao dịch nằm ngoài đợt này.

### BQL
1. Mở dashboard local, nhập admin key demo (chưa phải đăng nhập theo từng người).
2. Chọn khu thử nghiệm, xem danh sách và trạng thái thật trong database.
3. Xem chi tiết/ảnh/cờ AI; duyệt hoặc từ chối có lý do.
4. Sao chép nội dung tin đã duyệt để trưởng/phó đăng nhóm thủ công.

## 4. Global Constraints

- Chỉ bind `127.0.0.1`; không mở public, không tạo tunnel trong đợt local.
- Admin key và bridge key khác nhau. Browser chỉ giữ khóa trong bộ nhớ, không nhúng vào source hoặc lưu localStorage.
- Khu/người gửi ở màn thử là dữ liệu mô phỏng của developer; khi nối Zalo phải ánh xạ metadata đáng tin cậy. Không coi ID tự nhập là xác minh cư dân.
- Gemini không được tự duyệt, tự đổi quyền, tự thực hiện giao dịch hoặc kết luận một người lừa đảo.
- Giá/tình trạng không rõ từ ảnh phải để trống; hỏi người bán. Giá luôn được code kiểm tra là số nguyên VND không âm.
- Ảnh tối đa 4 MiB, 16 triệu pixel, PNG/JPEG/WebP. Kiểm tra bytes thật, không chỉ đuôi tên/MIME khai báo. Không tự tải URL tùy ý để tránh truy cập mạng nội bộ.
- Không giữ write transaction SQLite khi chờ Gemini; xử lý cập nhật đồng thời bằng kiểm tra revision của bản nháp.
- Dùng ID tin thật để chống xử lý trùng. Lưu lại cùng kết quả cho event đã xử lý thành công; tránh tạo hai tin hoặc gọi AI lại không cần thiết.
- Tin chờ duyệt/từ chối/đã bán không được xuất hiện trong tìm kiếm. Cách ly dữ liệu theo khu và quyền chủ tin bằng code.
- Không log API key, cookie, toàn bộ ảnh base64 hoặc dữ liệu hội thoại thật. private và database không được commit.

## 5. Review Focus

1. Event gửi lại khi người dùng refresh/retry: không nhân đôi bản nháp, trạng thái hay quyết định.
2. Hai người/cùng người ở hai khu: không dùng chung ngữ cảnh hoặc đọc ảnh/tin của nhau.
3. Gemini timeout, HTTP lỗi, trả JSON sai hoặc nội dung bị chặn: lỗi có kiểm soát, không để lộ khóa, không tạo tin rỗng.
4. Người gửi sửa giá/tình trạng hoặc đổi món: bản nháp đúng phiên; bản đã chờ duyệt không bị sửa âm thầm.
5. Nội dung chứa HTML/script, JSON đặc biệt, dấu nháy và xuống dòng: UI hiển thị như văn bản; adapter không hỏng JSON hoặc gửi nhầm reply.

## 6. Cấu trúc file dự kiến

```text
backend/
  app.py             # app factory, routes lệnh xác định và phân quyền
  ai.py              # Gemini client, schema output, validate ảnh
  intake.py          # luồng hội thoại AI, draft và chống xử lý trùng
  static/
    admin.html       # dashboard BQL local
    admin.css
    admin.js
    chat.html        # màn thử chat local cho developer, không phải app cư dân
    chat.js
tests/
  test_app.py        # nghiệp vụ đã có
  test_ai.py         # provider + hội thoại, mở rộng từ bản chưa triển khai
  test_ui.py        # browser tests nếu phù hợp sau khi chốt DOM
docs/
  brief-prd.md
  integration.md
  local-demo.md      # hướng dẫn + kịch bản nghiệm thu
run-local.ps1        # venv/config, chạy localhost, tùy chọn DPAPI
requirements.txt
requirements-dev.txt
private/             # ignored: SQLite, ảnh, cấu hình và keys
```

## 7. Các bước triển khai sau khi duyệt

### Chặng A — Khởi động bản nền
**Files:** requirements, run-local.ps1, test_app.py.
- [ ] Tạo `.venv`, cài dependencies vào đúng môi trường.
- [ ] Chạy riêng `test_app.py`; phải đạt 6 tests cũ trước khi thay đổi nghiệp vụ.
- [ ] Chạy backend, kiểm tra `/health` và `/docs`, không đụng session Zalo.
- [ ] Ghi hướng dẫn một lệnh khởi động và nơi lưu dữ liệu local.

**Xong khi:** restart backend vẫn còn tin thử; không có khóa trong Git.

### Chặng B — Gemini đọc text và ảnh
**Files:** backend/ai.py, tests/test_ai.py, requirements.
**Interface:** `extract(text, image, previous) -> Analysis`; `ImageInput` nhận MIME + base64; output chỉ gồm intent/field/query/cờ kiểm duyệt.
- [ ] Chạy tests provider viết trước để xác nhận fail vì thiếu implementation.
- [ ] Viết client Gemini có timeout, schema JSON và kiểm tra output bằng Pydantic.
- [ ] Validate ảnh, không tải URL tùy ý; không gửi ảnh sai/oversized tới Gemini.
- [ ] Kiểm tra bằng HTTP mock: inline image, JSON sai, 401/429/5xx, timeout, thiếu giá/tình trạng.
- [ ] Smoke Gemini thật bằng ảnh đồ vật thử được người dùng cho phép; không dùng dữ liệu riêng tư. Dùng key local, không in key.

**Xong khi:** ảnh/text tạo dữ liệu hợp lệ; không rõ thì null; lỗi API không tạo tin hoặc lộ khóa.

### Chặng C — Hội thoại đăng bán và tìm mua
**Files:** backend/intake.py, backend/app.py, tests/test_ai.py.
**Interface:** `POST /ai/events` dùng bridge key, có cùng identity như `/events` cộng ảnh tùy chọn. Trả reply, listing_id, status, missing_fields, hoặc kết quả tìm.
- [ ] Lưu draft nhiều lượt theo khu/người gửi, có revision và ID cố định.
- [ ] Hỏi trường thiếu bằng code; gửi tóm tắt và yêu cầu xác nhận trước pending.
- [ ] Bổ sung lệnh bắt đầu lại/hủy nháp để người bán đổi món rõ ràng.
- [ ] Dùng AI phân loại nhu cầu tìm mua; tìm từ khóa và lọc giá xác định, tối đa 5 kết quả.
- [ ] Lưu cờ kiểm duyệt, ảnh và metadata để BQL xem. Mọi tin vẫn cần người duyệt ở bản local.
- [ ] Test duplicate, tin tự gửi, tin nhóm, revision conflict, tách khu/chủ tin, confirm thiếu thông tin, báo đã bán.

**Xong khi:** một người trả lời 3–4 lượt tạo đúng một tin; người khác không đọc/sửa được tin đó; tìm không thấy tin chưa duyệt.

### Chặng D — Dashboard BQL
**Files:** backend/static/admin.*, backend/app.py, tests.
**Interfaces:** GET `/admin`, GET `/listings`, POST `/listings/{id}/review`, GET `/listings/{id}/image` có admin key và scope khu.
- [ ] Danh sách có lọc trạng thái, empty/loading/error states và nút tải lại.
- [ ] Chi tiết hiển thị tên, giá, tình trạng, ảnh, cờ AI và lý do.
- [ ] Duyệt/từ chối có lý do; vô hiệu hóa khi không còn pending; xử lý conflict khi đã được xử lý.
- [ ] Sao chép tin chỉ khi approved; thông báo rõ chưa đăng vào Zalo.
- [ ] Desktop/mobile, focus bàn phím, dữ liệu render bằng textContent, ảnh fetch bằng header rồi blob URL.
- [ ] Browser test duyệt thành công, từ chối, sai key, chuyển khu, nội dung script không thực thi.

**Xong khi:** BQL xử lý được tin thật từ database mà không cần gọi API bằng tay.

### Chặng E — Màn thử chat local và demo
**Files:** backend/static/chat.*, docs/local-demo.md, tests UI.
- [ ] Form bridge key, khu/người gửi thử, ô chat và tải ảnh; tất cả ghi rõ mô phỏng local.
- [ ] Hiển thị reply, preview ảnh, nút xác nhận và báo lỗi dễ hiểu; chống bấm gửi lặp khi đang chờ.
- [ ] Chạy kịch bản seller → confirm → BQL approve → buyer search → seller sold → search không còn.
- [ ] Test trên desktop và màn hình hẹp; chụp ảnh QA, kiểm tra lỗi console.
- [ ] Không tự tạo dữ liệu cư dân; seed chỉ khi có lệnh rõ ràng và nhãn dữ liệu demo.

**Xong khi:** bạn mở hai tab chat/dashboard và tự diễn được vòng nghiệp vụ mà không phụ thuộc listener Zalo.

### Chặng F — Nối Deplao, nghiệm thu riêng
**Files:** docs/integration.md, workflow mẫu chỉ khi xác minh source phiên bản.
- [ ] Kiểm tra listener bằng log nhận tin thật, không suy ra từ nút chạy thử hoặc cờ connected.
- [ ] Nếu cần quét QR, người dùng tự thao tác. Không xóa tài khoản hoặc đổi cài đặt bảo mật.
- [ ] Đối chiếu node HTTP: body serialization với dấu nháy/xuống dòng, lấy `data.reply`, chặn gửi nếu HTTP lỗi/ignored.
- [ ] Chỉ import workflow sau khi chọn đúng account, scope người thử và bridge secret local. Tắt workflow chatbot cũ để tránh hai phản hồi.
- [ ] Người dùng gửi tin từ Thiên Bảo; xác minh ba điểm: Deplao nhận event → backend có event → đúng hộp thoại nhận reply.
- [ ] Chỉ bật nhận ảnh khi adapter lấy được bytes từ nguồn Zalo được kiểm soát và giữ đúng message identity. Nếu chưa đạt, chốt text-only Zalo và ảnh qua màn local, ghi rõ giới hạn.

**Xong khi:** ít nhất một vòng chat thật được kiểm chứng; nếu chưa, báo chính xác điểm nghẽn. Backend local vẫn nghiệm thu riêng, không tuyên bố Zalo đã xong.

### Chặng G — Bàn giao local và GitHub
**Files:** README, docs/local-demo.md, plan, CI.
- [ ] Chạy toàn bộ tests và HTTP smoke; kiểm tra diff không có credentials/dữ liệu thật.
- [ ] Review code trước khi tuyên bố hoàn thành.
- [ ] Cập nhật checklist thực tế và hướng dẫn mở dashboard/chat, khởi động/dừng và dữ liệu ở đâu.
- [ ] Push vào nhánh PR #1 theo phạm vi GitHub đã yêu cầu; không tự merge main hoặc deploy public.
- [ ] Mở giao diện local để người dùng thử. Máy cần tiếp tục bật để demo.

## 8. Những việc chưa làm trong bản này
- Chưa Supabase/Postgres/pgvector hoặc tìm kiếm vector RAG; local dùng keyword + bộ lọc.
- Chưa Zalo OA/Mini App/Facebook, tự đăng nhóm hoặc bot trả lời trong nhóm.
- Chưa thu phí, kiểm chứng hóa đơn, phân bổ tài nguyên.
- Chưa login BQL từng người, định danh cư dân thật, xử lý thanh toán hoặc chuyển tiếp hội thoại ẩn danh.
- Chưa bảo đảm chạy 24/7, triển khai VPS, outbox gửi Zalo, production rate limit hoặc chính sách retention hoàn chỉnh.

## 9. Nội dung người dùng cần duyệt
1. Đồng ý local stack và UI thử chat + dashboard ở cùng backend.
2. Đồng ý MVP duyệt thủ công toàn bộ tin; nhóm chợ do trưởng/phó đăng thủ công.
3. Đồng ý Gemini cloud xử lý dữ liệu thử; tìm kiếm keyword trước, vector sau.
4. Đồng ý nghiệm thu local trước, Zalo thật là chặng riêng có phụ thuộc listener.

Sau khi duyệt mới cài dependencies, viết code tiếp và push thay đổi. Kế hoạch này chỉ được lưu local để người dùng xem.
