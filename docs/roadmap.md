# Roadmap workflow — ưu tiên trải nghiệm cư dân

> **For agentic workers:** Dùng superpowers:executing-plans khi người dùng chọn chặng thực hiện. Đây là kế hoạch trải nghiệm và phạm vi, không phải xác nhận các tính năng dưới đây đã hoạt động.

**Goal:** Cư dân bán/mua qua Zalo mà không phải nhớ lệnh, không bị mất ngữ cảnh, biết rõ trạng thái và có thể nhờ người hỗ trợ.

**Architecture:** Giữ3adapter Deplao đang bật: text private, image private, publisher v2. Luồng nghiệp vụ và quyền ở backend. Thêm1workflow gửi thông báo riêng qua outbox cho quyết định BQL, yêu cầu quan tâm và nhắc việc có kiểm soát. Không tạo một workflow Deplao cho từng chức năng nhỏ.

**Tech Stack:** Giữ local FastAPI/SQLite/Deplao/Gemini text/OpenAI image safety. Embedding, gợi ý giá và ảnh tương tự là các chặng riêng; chọn/cấu hình provider sau khi chốt tiêu chí, không giả đã tích hợp.

**Spec:** Phát triển từ yêu cầu ưu tiên UX của dự án; đối chiếu README và các hướng dẫn vận hành hiện tại.

## 1. Hiện trạng và phần còn thiếu

Đã có code cho đăng bán text tự nhiên, hỏi thiếu, xác nhận trần, duyệt, ảnh an toàn, tìm từ khóa/lookup mã, báo đã bán và publisher v2. Đã xác minh3workflow Deplao đang bật ngày14/11/2026. Việc một workflow bật không thay thế kiểm chứng từng vòng gửi thật.

Chưa có: thông báo kết quả duyệt riêng, sửa tin đang bán có phiên bản, quản lý tin của tôi, yêu cầu mua/kết nối hai bên, semantic search, gợi ý giá, đối chiếu ảnh/mô tả, tìm ảnh trùng, nhắc hết hạn đầy đủ.

## 2. Nguyên tắc trải nghiệm

- Chat riêng là nơi làm việc; nhóm chung chỉ trưng bày tin đã duyệt, ảnh và thông báo đã bán.
- Không bắt người dùng nhớ mã khi ngữ cảnh đủ rõ. Có nhiều món thì hỏi chọn, tuyệt đối không đoán.
- Cho phép câu tự nhiên và số thứ tự trong menu; không giả định Zalo cá nhân có native button/clipboard action chưa kiểm chứng.
- Một lần hỏi một thông tin, tận dụng điều người dùng đã nói. Chấp nhận trả lời giá/tình trạng/ảnh theo thứ tự khác nhau.
- Không yêu cầu gửi ảnh lại chỉ vì người dùng chưa viết đúng lệnh. Phải giữ ảnh tạm theo người/khu, có hạn lưu.
- Không nói đã lưu/duyệt/đăng/gửi/kết nối trước khi có bằng chứng từ code/receipt. Gửi thành công không có nghĩa đối phương đã đọc hoặc đồng ý.
- Lỗi không bắt đầu lại toàn bộ: giữ nháp, chỉ yêu cầu làm lại phần lỗi. Không in HTTP/CDN/key/traceback cho cư dân.
- Không công khai danh tính, số điện thoại hoặc nội dung private của hộ khác. Kết nối cần sự đồng ý rõ ràng.
- Không gửi thông báo dồn dập. Lặp event không lặp thao tác, không lặp thông báo. Có tắt nhắc việc và giờ yên tĩnh.

## 3. P0 — hoàn thiện trải nghiệm đang có

### WF01 — Chào hỏi và xác định nhu cầu
**Trigger:** người mới nhắn, câu chào, yêu cầu không rõ, hoặc yêu cầu trợ giúp.
**Flow:** nhận diện ý định → câu hướng dẫn ngắn → hỏi một bước tiếp theo → lưu ngữ cảnh.
**Ví dụ:** “Bạn muốn đăng bán, tìm mua hay xem tin của mình? Bạn có thể nhắn tự nhiên hoặc chọn1/2/3.”
**Demo:** người thử được gán khu demo có nhãn rõ. Trước khi mở thật phải có mapping cư dân/khu do BQL xác minh hoặc lời mời, không tin khu tự khai trong chat.
**Nghiệm thu:** cùng người/khu không bị chào lại mỗi tin; người mới không cần gõ ban/tim; không nhầm câu hỏi mua thành đăng bán.

### WF02 — Đăng bán linh hoạt, kể cả ảnh trước
**Trigger:** gửi ảnh, text, giá hoặc tình trạng.
**Flow:** giữ inbox draft → trích xuất những gì có căn cứ → gắn ảnh vào đúng draft → hỏi trường thiếu → tóm tắt → xác nhận.
**Ảnh trước:** nhận ảnh an toàn vào vùng tạm rồi hỏi “Bạn muốn bán món gì, giá dự kiến bao nhiêu?”; không ép gửi lại ảnh. Ảnh tạm chưa gắn tin xóa sau24giờ, không dùng lại cho giao dịch khác. Đọc món từ ảnh là bước riêng cần Gemini vision, không phải Moderation.
**Ví dụ:** “Mình bán ghế500k” → hỏi tình trạng → người dùng gửi ảnh và nói “dùng6tháng” → một nháp duy nhất.
**Nghiệm thu:** đổi thứ tự ảnh/text không mất dữ liệu; hủy/đổi món không kéo ảnh món cũ sang; ảnh lỗi giữ nguyên text; tối đa5ảnh như hiện tại.

### WF03 — Tin của tôi, xem trạng thái, sửa/hủy
**Trigger:** “tin của tôi”, “tin ghế tới đâu rồi”, “sửa giá”, “hủy tin”.
**Flow:** truy vấn đúng chủ tin/khu → danh sách ngắn có số thứ tự → chọn món → xem/sửa/hủy → xác nhận hành động.
**Ví dụ:** “Tin của tôi” → “1.Ghế—Chờ duyệt;2.Bàn—Đang bán” → “sửa giá món2 thành350k”.
**Quy tắc sửa:** nháp sửa trực tiếp và cho xem lại. Tin pending/approved tạo bản sửa mới chờ duyệt, bản cũ không bị thay âm thầm. Nếu muốn dừng bản cũ ngay, người bán chọn ẩn tin rõ ràng; không tự gỡ rồi mới báo.
**Nghiệm thu:** không sửa tin hộ khác; có nhiều món hỏi chọn; ảnh/mô tả mới vô hiệu hóa kết quả kiểm duyệt cũ; hủy có xác nhận và không thể bị tác vụ đang chạy ghi sống lại.

### WF04 — Thông báo kết quả BQL
**Trigger:** BQL duyệt, yêu cầu bổ sung, từ chối; publisher có receipt.
**Flow:** commit quyết định → enqueue private notification → Deplao gửi đúng hội thoại → ack → hiện kết quả.
**Tin nhắn:** “Tin ghế đã được duyệt. Hệ thống đang chờ đăng nhóm.” Sau receipt mới nói “Đã đăng vào nhóm…”. Từ chối phải có lý do và cách sửa, không chỉ báo một chữ “từ chối”.
**Nghiệm thu:** không phải tự hỏi bot mới biết; không gửi trùng; không báo đã đăng khi chỉ queued; lỗi gửi giữ job retry có kiểm soát.

### WF05 — Lỗi và chuyển BQL hỗ trợ
**Trigger:** API lỗi, bot hiểu sai nhiều lần, người dùng nhắn “gặp BQL”, tin bị tranh chấp.
**Flow:** nêu phần chưa xử lý → giữ nháp → thử lại phần lỗi hoặc tạo phiếu hỗ trợ → BQL tiếp nhận → trả lời lại hội thoại.
**Nghiệm thu:** không yêu cầu người dùng đăng nhập/quétQR cho lỗi hệ thống của Meo Meo; không đổ lỗi người dùng; không nói BQL đã nhận/đọc khi chưa có trạng thái tương ứng.

## 4. P1 — hoàn thành hành trình mua bán

### WF06 — Tìm mua tự nhiên và semantic search
**Trigger:** “cần ghế làm việc dưới700k”, “món thứ2 còn không”, gửi mã từ nhóm.
**Flow:** trích nhu cầu/giới hạn giá → semantic + keyword → code lọc khu/approved/còn bán/giá → tối đa vài thẻ → chọn số hoặc mã → chi tiết.
**Ngữ cảnh:** lưu snapshot danh sách theo người/khu, TTL30phút cho câu “món2”; hết hạn hỏi tìm lại. Luôn kiểm tra trạng thái hiện tại khi xem hoặc quan tâm.
**Nghiệm thu:** diễn đạt khác từ khóa vẫn tìm được món phù hợp; không nhầm ngân sách; chưa có kết quả thì xin nới tiêu chí, không bịa món hoặc bỏ bộ lọc âm thầm.

### WF07 — Quan tâm và kết nối hai bên có đồng ý
**Trigger:** người mua nhắn “quan tâm”, “muốn mua món2”.
**Flow:** chọn món → kiểm tra còn bán → xác nhận gửi yêu cầu → thông báo người bán → người bán chấp nhận/từ chối → báo người mua.
**MVP:** trước hết gửi yêu cầu và phản hồi qua bot, chưa hứa chat relay ẩn danh hoàn chỉnh. Chia sẻ liên hệ trực tiếp chỉ khi bên cung cấp đồng ý rõ ràng, mặc định không hiện SĐT.
**Nghiệm thu:** hỏi mua không tự đánh dấu đã bán/giữ chỗ; không gửi hàng loạt cho người bán; chặn tự hỏi mua tin của mình; cùng người/món không tạo nhiều yêu cầu đang mở.

### WF08 — Đã bán, hủy giao dịch và thông báo liên quan
**Trigger:** chỉ chủ tin xác nhận đã bán; báo nhầm/không giao dịch được.
**Flow:** nếu một món thì tóm tắt xác nhận; nhiều món hỏi chọn → sold → loại tìm kiếm → thông báo nhóm + những người đang quan tâm.
**Quy tắc:** người mua không được đóng tin của người bán. Chưa xây thanh toán nên không nói thanh toán/giao hàng đã hoàn tất. Mở bán lại là hành động riêng có xác nhận và xem xét duyệt lại, không đổi trạng thái bằng LLM.
**Nghiệm thu:** không thông báo sold hai lần; khi còn nhiều món không đoán; group post cũ chưa thu hồi phải có thông báo đúng mã như hiện tại.

## 5. P2 — tăng chất lượng và giảm việc BQL

### WF09 — Gợi ý giá có căn cứ
**Trigger:** “nên bán bao nhiêu”, chưa biết giá.
**Flow:** tìm món tương tự → kiểm tra số mẫu/độ tương đồng → code tính khoảng tham khảo → nêu nguồn/chất lượng dữ liệu → người bán chọn giá.
**Nghiệm thu:** dữ liệu ít thì nói chưa đủ; phân biệt giá rao và giá chốt; không chốt giá thay người bán; không đưa số chính xác giả từ LLM.

### WF10 — Ảnh không khớp và ảnh trùng
**Trigger:** nhận/đổi ảnh hoặc mô tả.
**Flow:** safety trước → đối chiếu ảnh/mô tả → hash/pHash tìm ứng viên trùng cùng khu → hỏi người bán gửi lại/sửa → đưa hai tin/ảnh cạnh nhau cho BQL.
**Nghiệm thu:** ảnh mờ báo chưa đủ thông tin; hai ghế cùng mẫu không tự bị coi là lừa đảo; không tiết lộ danh tính/ảnh nháp riêng của hộ khác cho cư dân. Cư dân chỉ nhận cảnh báo chung; BQL có quyền xem đối chiếu.

### WF11 — Nhắc hạn và dọn tin cũ
**Đề xuất mặc định để duyệt:** tin hết hạn sau14ngày, nhắc người bán trước24giờ một lần; không tự gia hạn. Nhắn “còn bán” để gia hạn14ngày sau xác nhận đúng món. Có tắt nhắc và không gửi nhắc ngoài8h–20h giờ Việt Nam.
**Nghiệm thu:** quá hạn bị loại khỏi tìm kiếm ngay cả khi lịch chạy bị tắt; không xóa dữ liệu để mất audit; không nhắc trùng; hỏi mua không tự gia hạn tin.

## 6. Giữ số workflow Deplao gọn

| Workflow hạ tầng | Trạng thái | Nghiệp vụ phục vụ |
|---|---|---|
| Private Text Intake | Có | WF01/02/03/05/06/07/08/09 |
| Private Image Intake | Có | WF02/10 |
| Group Publisher v2 | Có | Đăng bài, ảnh, mã, thông báo sold |
| Private Notification Delivery | Cần thêm | WF04/05/07/08/11 |

Backend định tuyến intent và kiểm tra quyền. Maintenance/expiry tạo jobs trong backend; có thể chạy tick cùng lượt claim của private notifier ở local, không cần thêm workflow cho mỗi loại nhắc. Không dùng LLM tự chọn người nhận thông báo.

## 7. Thứ tự triển khai được đề xuất

1. **Sprint1 — người dùng không bị lạc:** WF01 + WF03 + WF04 + WF05. Cư dân biết làm gì, tin đang ở đâu, BQL trả lời gì. Chưa đổi search hoặc thêm model mới.
2. **Sprint2 — đăng bán không phải làm lại:** hoàn thiện WF02 với ảnh trước/text trước, xử lý nháp dở và sửa thông tin.
3. **Sprint3 — mua được món:** WF06 + WF07. Semantic search trước, sau đó request kết nối có đồng ý.
4. **Sprint4 — vòng đời rõ ràng:** hoàn thiện WF08 + WF11, expiry và thông báo người quan tâm.
5. **Sprint5 — hỗ trợ thông minh:** WF09 + WF10 sau khi có dữ liệu so sánh và bộ ảnh đánh giá.

Mỗi sprint chỉ kết thúc khi chạy được bằng tài khoản thử thật qua Zalo, có kiểm tra account khác/khu khác và phục hồi khi mất kết nối. Không lấy nút “chạy thử” làm bằng chứng end-to-end.

## 8. Đo trải nghiệm bằng dữ liệu thử

- Người mới hoàn thành một tin bán mà không được người xây hệ thống hướng dẫn trực tiếp.
- Đếm số lần bot hỏi lại thông tin đã có, bắt gửi lại ảnh, chọn sai món: tiêu chí lỗi cần sửa, không đổ cho người dùng.
- Đếm số lượt cần để tạo nháp và tìm được món; so sánh trước/sau, chưa hứa giảm một tỷ lệ khi chưa đo.
- Mọi quyết định duyệt phải có kết quả gửi thông báo hoặc trạng thái lỗi rõ, không có tin mất dấu.
- 5người thử đóng vai bán/mua/BQL, dùng các câu diễn đạt khác nhau; không chỉ một tài khoản Thiên Bảo.
- Không xuất dữ liệu riêng tư giữa người dùng/khu trong cả happy path và trường hợp lỗi.

## 9. Nghiệm thu Sprint1 trước khi bắt đầu Sprint2

- [ ] Người mới nhắn “chào”, chọn việc bằng lời tự nhiên/số mà không lặp menu mỗi tin.
- [ ] Chủ tin nhắn “tin của tôi” thấy đúng tin của mình, người khác không xem được.
- [ ] Chọn món rồi sửa giá; bot tóm tắt thay đổi trước khi xác nhận, không sửa nhầm món.
- [ ] BQL từ chối kèm lý do; đúng người bán nhận được lý do và hướng dẫn sửa.
- [ ] BQL duyệt; bot phân biệt đã duyệt/đang chờ đăng/đã có receipt đăng nhóm.
- [ ] Tắt kết nối rồi bật lại; private notification không gửi nhầm người hoặc nhân đôi.
- [ ] Người dùng yêu cầu BQL hỗ trợ; có mã phiếu và trạng thái thật, không hứa thời gian chưa có SLA.

## 10. Các phần cần chốt riêng trước khi triển khai

- Sửa tin approved: giữ bản cũ trong lúc duyệt bản sửa hay cho người bán ẩn ngay — đề xuất giữ bản cũ và đưa tùy chọn ẩn rõ ràng.
- Kết nối hai bên: chốt thông báo quan tâm trước, chưa chia sẻ SĐT và chưa xây relay chat đầy đủ.
- Duyệt mặc định expiry14ngày và giờ nhắc8h–20h hoặc thay theo BQL.
- Định danh cư dân thật, đăng nhập BQL theo cá nhân và vận hành liên tục phải hoàn thành trước khi mở rộng ra ngoài nhóm thử. Local hiện tại không tự trở thành hệ thống production.

Tài liệu này chỉ lập kế hoạch. Không tự bật thông báo, gửi tin mới hoặc triển khai các workflow chưa được chọn trong lượt này.
