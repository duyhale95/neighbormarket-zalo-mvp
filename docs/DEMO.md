# Demo NeighborMarket cho mentor

## Phạm vi đã kiểm chứng

Bộ kiểm thử chạy toàn bộ nghiệp vụ với HTTP in-process và bộ gửi nhóm giả lập. Chưa có bằng chứng tin nhắn Zalo thật kích hoạt Deplao, tới backend và được gửi vào nhóm Legit. Không có workflow marketplace importable đã được xác thực; workflow Gemini có sẵn là chatbot độc lập, không kết nối các API marketplace. Không đưa token, cookie, khóa hoặc hội thoại thực vào repository hay demo.

## 1. Chuẩn bị trên Windows

Cần Python 3.11+ và PowerShell 7. Trong PowerShell tại repository:

```powershell
Set-Location C:\Users\Admin\neighbormarket-zalo-mvp
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:ZALO_COMMUNITY_ID = 'demo'
$env:ZALO_LEGIT_GROUP_ID = 'mock-legit-group'
pwsh -File .\run-local.ps1
```

Giữ cửa sổ đang chạy mở và truy cập http://127.0.0.1:8000/docs. `run-local.ps1` tạo hai khóa demo khác nhau tại `private/local-config.json`, thiết lập database `private/market.db`, rồi chạy server chỉ trên localhost. Nhập khóa phù hợp trong Swagger khi được yêu cầu: `bridge_key` cho `/events` và API claim/sent/failure, `admin_key` cho danh sách và duyệt. Không chia sẻ hoặc commit file này. Trong ví dụ mock, group ID là nhãn giả, không phải nhóm Zalo thật.

Đặt group ID và community **trước khi approve**: chỉ tin chuyển từ pending sang approved trong community được cấu hình mới tạo job cho group đã cấu hình. Không có tự động backfill cho tin được duyệt trước khi cấu hình group. Dùng database demo mới hoặc tạo và duyệt một tin mới để trình diễn. Không sửa/xóa database đang dùng mà chưa sao lưu dữ liệu cần giữ.

### AI tùy chọn

Mặc định AI tắt; toàn bộ demo dưới đây dùng lệnh xác định và không cần API trả phí. Nếu chủ tài khoản đã chủ động cấu hình OpenAI, thiết lập `AI_ENABLED=true`, `OPENAI_API_KEY` và `OPENAI_MODEL` trong môi trường trước khi chạy backend. Không ghi khóa vào file commit hoặc tài liệu. Khi thiếu khóa hoặc dịch vụ lỗi, bot hướng dẫn dùng các lệnh xác định; AI chỉ trích xuất, không tự duyệt hay đăng nhóm. Xử lý thiếu dữ liệu yêu cầu người dùng gửi lại đủ thông tin; chưa có hội thoại nhiều lượt để ghép dữ liệu.

## 2. Chạy demo tự động không gửi Zalo

Mở PowerShell thứ hai:

```powershell
Set-Location C:\Users\Admin\neighbormarket-zalo-mvp
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_demo_smoke.py -v
```

Test tạo SQLite tạm, adapter intake và backend trong cùng tiến trình. Một mock sender lưu bài vào danh sách trong bộ nhớ: không kết nối Zalo hoặc thực hiện outbound thật. Kịch bản kiểm tra:

1. Event người bán vào `/intake` tạo draft; gửi lại cùng message ID không tạo tin thứ hai.
2. Người bán gửi `xacnhan MÃ_TIN`; tin thành pending.
3. BQL approve; duyệt lại bị 409 và không tạo job thứ hai.
4. Bridge claim một job cho `mock-legit-group`; bộ gửi giả lập nhận bài đã chuẩn hóa; bridge gửi ACK với ID giả.
5. Delivery thành `sent`; claim lại trả 204 và mock sender chỉ nhận một bài.
6. Event người mua `tim ghe` trả mã tin đã duyệt.

Chạy đầy đủ bộ kiểm thử bằng `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`. Python mặc định trên máy có thể là Anaconda không cài FastAPI; dùng đúng Python trong `.venv`.

## 3. Kịch bản trình diễn API thủ công

Đây là đường dự phòng khi Zalo/Deplao mất kết nối. Dùng dữ liệu giả, Swagger và các khóa local; bước gửi nhóm là mô phỏng, không chứng minh Zalo hoạt động.

1. `POST /events` bằng bridge key, với `event_id` duy nhất, `community_id` là `demo`, `sender_id` là `seller-demo`, `thread_type` là `private`, `is_self` là `false`, và `text` là `ban Ghế làm việc | 500000 | đã dùng 6 tháng`. Ghi mã `listing_id` từ phản hồi `draft`.
2. Gửi event mới với ID mới, cùng community/sender, text `xacnhan MÃ_TIN`. Kiểm tra kết quả `pending`.
3. `GET /listings?community_id=demo` bằng admin key; `POST /listings/MÃ_TIN/review` với `{"community_id":"demo","action":"approve","reason":"Đã kiểm tra"}`. BQL tự xem nội dung và cờ kiểm duyệt trước khi quyết định. Kết quả `delivery_status: queued` nghĩa là job đã được tạo; `not_configured` nghĩa là không tạo job do chưa có group hoặc community không khớp. Trường hợp reject dùng `action: reject` và lý do; kết quả `not_applicable`, không có job đăng.
4. `POST /deliveries/claim` bằng bridge key. Kiểm tra group ID và bài đã chuẩn hóa. Với **mock**, giả lập đã gửi; gọi `POST /deliveries/DELIVERY_ID/sent` với `{"claim_token":"TOKEN_TỪ_CLAIM","sent_message_id":"mock-message-1"}`. Token là thông tin nhạy cảm: chỉ dùng local, không chia sẻ hoặc commit.
5. Kiểm tra `GET /deliveries?community_id=demo` bằng admin key: trạng thái `sent` trong kịch bản này chỉ ghi nhận ACK giả lập. Gọi claim lần nữa nhận 204 nếu không còn job khác.
6. Người mua giả gửi `POST /events` với sender và event ID khác, text `tim ghe`; kiểm tra kết quả có mã tin. Chủ tin có thể gửi `daban MÃ_TIN`, rồi tìm lại để thấy tin không còn trong kết quả.

Nếu không chắc gửi thật thành công, không ACK thành công và không tự gửi lại. Bridge báo `/deliveries/DELIVERY_ID/failure` với `outcome: unknown`, `claim_token` và lỗi ngắn như `timeout`; claim hết hạn cũng chuyển `unknown`. BQL đối chiếu nhóm thực tế, sau đó dùng API admin `/deliveries/DELIVERY_ID/reconcile` với quyết định `sent` hoặc `not_sent` và lý do. `not_sent` chuyển `failed`, không tự đưa vào hàng chờ lại.

## 4. Kiểm tra Deplao và chuẩn bị live

Người dùng tự tạo/cấu hình nhóm và quyền: BQL là trưởng nhóm, Meo Meo là phó nhóm, cư dân chỉ đọc nếu Zalo hỗ trợ. Người dùng tự kiểm tra trên tài khoản thật rằng Meo Meo gửi được vào nhóm; không thay đổi quyền nhóm tự động. Thay group ID giả bằng ID nhóm đã cho phép trước khi khởi động lại backend và duyệt tin mới.

Trong Deplao trên máy demo:

1. Xác nhận Meo Meo đang kết nối và listener đang hoạt động. Từ một tài khoản khác gửi PM thử không chứa dữ liệu nhạy cảm; kiểm tra sự kiện xuất hiện trong Deplao và workflow execution history. Tin đến điện thoại hoặc chạy workflow thủ công thành công chưa chứng minh listener đang chạy.
2. Kiểm tra workflow đã bật và chỉ gắn tài khoản Meo Meo; trigger `trigger.message` có `threadType` là `0`, `ignoreOwn=true`, `senderRole=all`. Bỏ các bộ lọc `fromId`, `groupId`, keyword, exclusion, thời gian hoạt động, cooldown/debounce nếu không chủ đích; nếu lọc loại tin, chọn tin văn bản phù hợp.
3. Nếu không nhận sự kiện, xem trạng thái kết nối, log lỗi và thử kết nối lại hoặc đăng nhập lại qua UI. Việc không có execution history chỉ thu hẹp nơi cần kiểm tra; chưa đủ để kết luận nguyên nhân. Không gửi log chứa nội dung PM, cookie hoặc thông tin phiên.
4. `workflows/meo-meo-auto-reply-private.json` có thể import để kiểm tra workflow Gemini cũ nếu đã có cấu hình cần thiết; chọn Meo Meo, chọn trợ lý, lưu và bật, tắt workflow cũ trùng lặp. Workflow này **không** kết nối backend marketplace và không chứng minh luồng xuất bản. Không có workflow intake/publisher nào được xác thực để import cho demo marketplace tại thời điểm viết tài liệu này.
5. Một connector thật cần nhận metadata message ID ổn định, sender ID và thread ID từ Zalo, xác thực caller tới `/intake`, map community đáng tin cậy, JSON-encode nội dung an toàn và trả đúng `reply` về thread gốc. `backend/intake_bridge.py` cung cấp adapter HTTP có xác thực, nhưng chưa kết nối được Deplao tự động. Không lấy identity hoặc group ID từ nội dung PM; không hardcode key trong workflow.
6. Sau khi có connector đã xác minh, mới thử đủ vòng: người bán PM → draft → xác nhận → BQL approve → gửi bài trong group → ACK → người mua PM tìm. Kiểm tra nội dung bài và ID nhóm, trạng thái delivery và chạy lại publisher để đối chiếu không đăng trùng. Chưa thể đánh dấu các bước live này đã thành công khi chưa thử trên tài khoản và nhóm thực.

## 5. Giới hạn và bằng chứng Deplao

Source upstream được kiểm tra tại commit [`2162f077d49f3b990121717fe6596fb3f0941e2f`](https://github.com/babyvibe/deplao-builder/tree/2162f077d49f3b990121717fe6596fb3f0941e2f), chưa xác nhận trùng với bản cài trên máy. [Listener upstream](https://github.com/babyvibe/deplao-builder/blob/2162f077d49f3b990121717fe6596fb3f0941e2f/src/utils/zalo/ZaloLoginHelper.ts#L735-L752) ghi raw message và content vào log. [Workflow engine](https://github.com/babyvibe/deplao-builder/blob/2162f077d49f3b990121717fe6596fb3f0941e2f/src/services/workflow/WorkflowEngineService.ts#L1673-L1728) lưu input/output của node; HTTP node cũng đưa headers/body vào output, và sendMessage ghi nội dung. Vì vậy không thể bảo đảm yêu cầu không log PM nhạy cảm với phiên bản upstream này nếu chưa xử lý và xác minh chính sách log trên bản cài; chỉ dùng dữ liệu giả trong demo.

[Template engine](https://github.com/babyvibe/deplao-builder/blob/2162f077d49f3b990121717fe6596fb3f0941e2f/src/services/workflow/WorkflowEngineService.ts#L4768-L4773) render chuỗi top-level và [thay giá trị thô](https://github.com/babyvibe/deplao-builder/blob/2162f077d49f3b990121717fe6596fb3f0941e2f/src/services/workflow/WorkflowEngineService.ts#L4822-L4854), không chứng minh JSON escaping an toàn. [HTTP node](https://github.com/babyvibe/deplao-builder/blob/2162f077d49f3b990121717fe6596fb3f0941e2f/src/services/workflow/WorkflowEngineService.ts#L2736-L2781) trả status 0 khi lỗi mạng và không tự dừng với 4xx/5xx. [Send node](https://github.com/babyvibe/deplao-builder/blob/2162f077d49f3b990121717fe6596fb3f0941e2f/src/services/workflow/WorkflowEngineService.ts#L2218-L2236) không đủ để suy ra gửi chắc chắn khi mất ACK; không bật `continueOnError` rồi tin mặc định success. Xác minh mapping và phiên bản thực tế trước mọi tích hợp live.

Các giới hạn demo khác: khóa BQL dùng chung không thay thế đăng nhập/phân quyền; chưa chứng minh danh tính cư dân; không có đảm bảo gửi reply PM đúng một lần; mock không xác minh quyền gửi group hay message ID thật; không có xử lý ảnh. Delivery `unknown` cần người đối soát và không được tự retry.

