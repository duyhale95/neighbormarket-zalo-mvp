'use client';
import { useState } from 'react';
import { Plus } from 'lucide-react';
const questions = [
  [
    'NeighborMarket AI là gì?',
    'Một dự án MVP về trợ lý chợ cư dân: hỗ trợ tạo nháp, xác nhận, BQL kiểm duyệt và tìm món đồ đang bán. Backend và luồng gửi giả lập đã được kiểm thử; dự án là demo độc lập.',
  ],
  [
    'Cư dân đăng bán sản phẩm như thế nào?',
    'Luồng dự kiến là nhắn riêng cho Meo Meo. Backend hỗ trợ lệnh “ban Tên món | Giá VND | Tình trạng”, sau đó người bán xác nhận để gửi BQL. AI trích xuất ngôn ngữ tự nhiên là tùy chọn; connector Zalo thật vẫn cần xác minh.',
  ],
  [
    'Vì sao tin đăng cần BQL duyệt?',
    'Ban Quản lý kiểm tra nội dung, thông tin nhạy cảm và tính phù hợp với cộng đồng trước khi tin vào hàng chờ xuất bản. Cờ AI chỉ hỗ trợ, không thay thế quyết định của con người.',
  ],
  [
    'AI có tự động đăng tin khi chưa được duyệt không?',
    'Không. AI chỉ hỗ trợ trích xuất và gợi ý kiểm tra. Backend kiểm soát trạng thái và chỉ tạo delivery cho tin đã được BQL duyệt, khi nhóm và community đã cấu hình đúng.',
  ],
  [
    'Dự án đã hoạt động trực tiếp trên Zalo chưa?',
    'Chưa có bằng chứng xác minh luồng Zalo thật. Backend, adapter và outbox đã được kiểm thử bằng dữ liệu và bộ gửi giả lập. Listener Deplao, ánh xạ metadata, quyền gửi nhóm và kết quả gửi thật vẫn cần thử trên tài khoản thực tế.',
  ],
  [
    'Dữ liệu trên trang giới thiệu có phải dữ liệu cư dân thật?',
    'Không. Các cuộc trò chuyện, tình huống và dashboard preview đều là minh họa. Không gian BQL sau đăng nhập đọc dữ liệu trực tiếp từ backend được cấu hình.',
  ],
];
export function FAQ() {
  const [opened, setOpened] = useState<number | null>(0);
  return (
    <section className="faq-section section-wrap" id="faq">
      <div className="faq-intro">
        <span className="section-kicker">NHỮNG ĐIỀU BẠN MUỐN BIẾT</span>
        <h2>
          Rõ ràng hơn.
          <br />
          An tâm hơn.
        </h2>
        <p>
          Về cách hoạt động, vai trò của AI
          <br />
          và trạng thái hiện tại của dự án.
        </p>
        <span className="faq-decoration" aria-hidden="true">
          ?
        </span>
      </div>
      <div className="faq-list">
        {questions.map(([q, a], index) => (
          <article className={`faq-item ${opened === index ? 'open' : ''}`} key={q}>
            <h3>
              <button
                aria-expanded={opened === index}
                aria-controls={`answer-${index}`}
                id={`question-${index}`}
                onClick={() => setOpened(opened === index ? null : index)}
              >
                {q}
                <Plus size={19} />
              </button>
            </h3>
            <div
              className="faq-answer"
              id={`answer-${index}`}
              role="region"
              aria-labelledby={`question-${index}`}
              inert={opened !== index}
            >
              <div>
                <p>{a}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
