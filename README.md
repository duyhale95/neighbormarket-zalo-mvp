# NeighborMarket AI — Zalo Legit MVP

> **Trạng thái (14/11/2026):** đã tích hợp ảnh private, BQL duyệt ảnh, publisher
> nhiều phần (ảnh bìa → ảnh thêm → mã tin) và thông báo đã bán; kiểm thử bằng dữ
> liệu tổng hợp, mock transport và trình duyệt. **Zalo thật, Deplao đang cài và
> moderation OpenAI thật vẫn CHƯA xác minh / chưa gọi.** Xem
> [trạng thái và kết quả kiểm thử](docs/MAIN_INTEGRATION_CHECKPOINT.md).

### Đã làm và đã kiểm thử, so với chưa xác minh

| Hạng mục | Trạng thái |
| --- | --- |
| Hội thoại nháp → xác nhận → BQL duyệt/từ chối → tìm kiếm → đã bán | Đã cài, test tự động |
| Ảnh: chuẩn hóa, lưu private, BQL xem/tải/kiểm tra lại, token phiên bản, bằng chứng thủ công | Đã cài, test backend + HTTP BFF + Edge |
| Publisher `photos_v2`, receipt từng phần, đối soát từng phần, sold notice | Đã cài, **mock** transport |
| Moderation ảnh OpenAI (`IMAGE_MODERATION_ENABLED`) | Tùy chọn, **chưa từng gọi thật** |
| Nhận ảnh/PM thật, gửi nhóm thật, receipt Zalo thật | **Chưa xác minh**; live bị khóa bởi [gate Deplao](docs/DEPLAO_COMPATIBILITY.md) |
| Cài đặt thủ công còn cần | Build Deplao strict, bind Meo Meo, quyền nhóm, tắt workflow cũ ([cleanup](docs/WORKFLOW_CLEANUP.md)) |

Chạy cả hai demo offline (không Zalo, không model trả phí):

```powershell
.\.venv\Scripts\python.exe -m tools.offline_demo
.\.venv\Scripts\python.exe -m tools.offline_media_demo
```

Biến mới (xem `.env.example`): `ZALO_PUBLICATION_MODE=single|photos_v2` (chỉ áp
dụng cho lần duyệt mới), `IMAGE_MODERATION_ENABLED/_API_KEY/_MODEL`,
`ZALO_IMAGES_ENABLED` (chỉ có hiệu lực khi manifest private đã xác nhận). Generator
giờ ghi `private/deplao-intake.json`, `private/deplao-publisher-v2.json`,
`private/zalo-channel.json` và tùy chọn `private/deplao-image-intake.json`.

## Partner workflow integration

Nhánh `feat/integrate-partner-zalo-workflow` bổ sung adapter Deplao text an toàn,
generator intake/publisher giữ file có khóa trong `private/`, hội thoại nháp có
hỏi bổ sung/sửa/hủy, moderation có lý do và nhãn nguồn/ACK trên BQL. Backend,
database, lifecycle và đăng nhập BQL hiện có tiếp tục là nguồn dữ liệu chính.

Chạy demo toàn bộ **không gửi Zalo, không gọi AI trả phí**:

```powershell
.\.venv\Scripts\python.exe -m tools.offline_demo
```

Kết quả ghi rõ `SIMULATED — NO REAL ZALO`, `transport_mode=mock`. Đọc
[kịch bản mentor, startup Windows, import Deplao và checklist live](docs/MENTOR_LIVE_DEMO.md)
và [mapping/decision log của ba nguồn](docs/PARTNER_INTEGRATION_PLAN.md).
**Chưa xác minh listener/PM/đăng nhóm trên Deplao cài tại máy.** Import workflow
không tự bind tài khoản. **Live hiện bị khóa:** engine Deplao đã khảo sát có
fallback sang account khác. Generator yêu cầu source đã sửa strict binding và
operator xác minh đúng bản đang chạy; xem [compatibility gate](docs/DEPLAO_COMPATIBILITY.md).
Không bật workflow cũ để bỏ qua kiểm tra này. Chỉ thử live sau khi kiểm tra
chính sách, account và nhóm.
Không chạy partner Bot Platform poller cùng Meo Meo; token đó khác session Deplao.
Mọi tin vẫn phải được người bán xác nhận và BQL duyệt. Ảnh được lưu private và
BQL phải xem; không có AI hiểu ảnh hay xác minh hàng thật (moderation chỉ gắn
cờ nội dung, tùy chọn, mặc định tắt). Xem [attribution MIT](THIRD_PARTY_NOTICES.md).

## Golden Sunrise frontend & BQL UI

Giao diện Next.js nằm trong `frontend/`: landing page `/`, đăng nhập `/bql/login`,
tổng quan `/bql`, hàng đợi `/bql/listings`, delivery `/bql/deliveries`. BQL đọc dữ
liệu FastAPI thật qua BFF server và duyệt/đối soát bằng API hiện có. Logo PNG gốc
do người dùng cung cấp đã được chép nguyên bản vào `assets/` và `frontend/public/brand/`.
Đây là demo độc lập, không có liên kết hoặc bảo trợ chính thức từ Vinhomes/Zalo/VinAI.

Chạy backend theo hướng dẫn bên dưới, rồi trong `frontend/` chạy `npm ci`, sao
chép `.env.example` thành `.env.local` nếu chưa có và cấu hình `BACKEND_URL`,
`ADMIN_API_KEY`, `BQL_DEMO_PASSWORD`, `BQL_SESSION_SECRET`, `APP_ORIGIN`,
`BQL_COMMUNITY_ID`. Chạy `npm run dev`, mở `http://127.0.0.1:3000` và đăng nhập
bằng mật khẩu BQL đã đặt. Khóa admin chỉ ở server, không nhập vào trình duyệt.
Thiếu cấu hình thì dashboard khóa truy cập và hiển thị hướng dẫn.

Xem [hướng dẫn Windows, bảo mật, kiểm thử và visual demo](docs/FRONTEND.md).
Landing dùng dữ liệu minh họa có nhãn; dashboard đọc backend được cấu hình.
Connector Zalo thật vẫn chưa được xác minh. Community Monitoring, Risk Alerts
và MLOps chỉ là mục “Đang phát triển”.

Backend chợ cư dân cho phép tạo bản nháp qua tin nhắn riêng, xác nhận, BQL duyệt, tìm tin và đánh dấu đã bán. Với nhóm đã cấu hình, việc duyệt tạo job đăng nhóm trong SQLite; bridge claim, báo kết quả gửi và cho phép BQL đối soát khi kết quả chưa rõ.

**Trạng thái demo:** luồng từ intake đến bài đăng nhóm và tìm kiếm đã được kiểm thử bằng HTTP và bộ gửi giả lập. Chưa có bằng chứng Deplao nhận PM thật và nối với backend, hoặc Meo Meo đăng được vào nhóm Legit. Đã có generator workflow importable đối chiếu source; chưa nghiệm thu trên ứng dụng Deplao đang cài. Workflow Gemini cũ chạy độc lập và phải tắt khi bật intake mới. Xem [kịch bản demo và giới hạn](docs/DEMO.md).

## Chạy trên Windows

Cần Python 3.11+ và Windows PowerShell 5.1 hoặc PowerShell 7. Tại repository:

```powershell
if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:ZALO_COMMUNITY_ID = 'demo'
$env:ZALO_LEGIT_GROUP_ID = 'mock-legit-group'
.\run-local.ps1
```

Mở [Swagger trên localhost](http://127.0.0.1:8000/docs). Script tạo các khóa demo khác nhau trong `private/local-config.json` nếu file chưa tồn tại và dùng `private/market.db`. Dùng bridge key cho `/events` và API delivery dành cho bridge; admin key cho `/listings`, review, danh sách delivery và đối soát. BQL có thể dùng dashboard Next.js theo hướng dẫn ở đầu README hoặc gọi API qua Swagger. Không chia sẻ hoặc commit file private và không dùng dữ liệu thật trong demo mock.

Cấu hình group ID và community **trước khi duyệt**. Nếu cấu hình thiếu hoặc community không khớp, phản hồi approve là `delivery_status: not_configured`: tin được duyệt nhưng không có job, và hệ thống không tự tạo lại job sau này. `mock-legit-group` chỉ là nhãn giả, không gửi được Zalo. Tự tạo tin mới sau khi cấu hình đúng để thử; không xóa database chưa sao lưu.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_demo_smoke.py -v
```

Bộ test dùng dữ liệu giả và không gửi tin Zalo thật. Chi tiết API và trạng thái connector xem [hợp đồng tích hợp](docs/integration.md).

## Thống kê và theo dõi

Trong Swagger, BQL dùng admin key gọi `GET /stats?community_id=demo` để xem tổng tin, pending, approved, rejected, sold và số delivery sent. Backend phát log JSON cho event, duyệt và delivery với một danh sách trường metadata được chọn; nội dung PM và khóa không nằm trong các trường audit này. Event ID trong log là SHA-256 của ID gốc và cũng được dùng làm mã tương quan; giá trị băm ổn định không bảo đảm ẩn danh, nên vẫn cần bảo vệ log. Một `sent` do mock ACK ghi chỉ chứng minh mock đã ACK, không chứng minh tin Zalo thật đã gửi.

## AI và kiểm duyệt

AI mặc định tắt; lệnh `ban`, `xacnhan`, `tim`, `daban` không cần API key. Tùy chọn bật OpenAI bằng `AI_ENABLED=true`, `OPENAI_API_KEY` và `OPENAI_MODEL` trong môi trường trước khi chạy. Chỉ bật nếu chủ tài khoản đã cấu hình và chấp nhận gửi nội dung PM tới dịch vụ API; không commit khóa hoặc nội dung PM. Khi AI không khả dụng, bot hướng dẫn các lệnh xác định. AI chỉ gợi ý dữ liệu nháp, không duyệt hoặc đăng nhóm; khi thiếu thông tin, người bán cần gửi lại đầy đủ thay vì bổ sung qua nhiều lượt.

BQL phải tự kiểm tra mọi tin. Cờ kiểm duyệt là heuristic, có thể bỏ sót hoặc báo nhầm; nội dung có cờ thông tin nhạy cảm không được duyệt. Backend không ghi log token hoặc PM chủ động, nhưng bản upstream Deplao đã xem có thể lưu raw message, node input/output và HTTP headers/body: chỉ dùng dữ liệu giả và xem [bằng chứng cùng hướng dẫn kiểm tra](docs/DEMO.md#5-giới-hạn-và-bằng-chứng-deplao) trước khi thử live.

## Giới hạn

Chưa xác minh listener Deplao, ánh xạ metadata (text và ảnh), workflow publisher, quyền gửi nhóm hoặc kết quả gửi Zalo thật; chưa có đảm bảo gửi reply PM đúng một lần. Chưa có xác thực cư dân hoặc tài khoản BQL riêng. Không hỗ trợ bổ sung ảnh cho tin đã duyệt (tránh sửa nội dung đã duyệt âm thầm) và không thu hồi bài đã đăng. Kết quả gửi không chắc chắn được đánh dấu `unknown` để BQL đối soát, không tự retry. Xem [brief sản phẩm](docs/brief-prd.md) và [Deplao Builder upstream](https://github.com/babyvibe/deplao-builder).
