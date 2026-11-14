import {
  ArrowUpRight,
  FileCheck2,
  Fingerprint,
  MessagesSquare,
  Search,
  ShieldCheck,
} from 'lucide-react';
import { Reveal } from './reveal';
export function Features() {
  return (
    <section className="features section-wrap" id="kiem-duyet">
      <Reveal>
        <div className="section-header inline-header">
          <div>
            <span className="section-kicker">THÔNG MINH VỪA ĐỦ. TIN CẬY DÀI LÂU.</span>
            <h2>
              Công nghệ ở phía sau.
              <br />
              Sự an tâm ở phía trước.
            </h2>
          </div>
          <p>
            Không thay thế sự quan tâm của con người.
            <br />
            Giúp mỗi quyết định có thêm thông tin.
          </p>
        </div>
      </Reveal>
      <div className="feature-layout">
        <Reveal className="feature-spotlight">
          <div className="feature-icon">
            <MessagesSquare size={25} strokeWidth={1.5} />
          </div>
          <span className="mini-kicker">AI LISTING ASSISTANT</span>
          <h3>
            Từ lời nhắn quen thuộc
            <br />
            đến một bản nháp rõ ràng.
          </h3>
          <p>
            AI tùy chọn hỗ trợ trích xuất tên, giá và tình trạng. Thiếu thông tin thì hỏi lại; người
            bán luôn kiểm tra trước khi xác nhận.
          </p>
          <div className="extraction-visual">
            <div className="extraction-input">
              “Bán bàn học gỗ, 450 nghìn,
              <br />
              đã sử dụng 1 năm…”<span>01 / TIN NHẮN</span>
            </div>
            <div className="extraction-line">
              <i />
              <span>TRÍCH XUẤT CÓ KIỂM TRA</span>
              <i />
            </div>
            <div className="extraction-fields">
              <span>
                Sản phẩm<strong>Bàn học gỗ</strong>
              </span>
              <span>
                Giá bán<strong>450.000đ</strong>
              </span>
              <span>
                Tình trạng<strong>Đã sử dụng 1 năm</strong>
              </span>
            </div>
          </div>
          <small className="feature-demo">Ví dụ minh họa · AI tắt nếu chưa được cấu hình</small>
        </Reveal>
        <div className="feature-rows">
          {[
            {
              Icon: ShieldCheck,
              title: 'Con người duyệt từng tin.',
              text: 'AI gợi ý kiểm tra. Ban Quản lý quyết định phê duyệt hoặc từ chối, kèm lý do.',
            },
            {
              Icon: FileCheck2,
              title: 'Xuất bản có kiểm soát.',
              text: 'Tin được duyệt vào outbox của nhóm đã cấu hình. Luồng gửi Zalo thật đang chờ xác minh.',
            },
            {
              Icon: Search,
              title: 'Tìm mua qua trò chuyện riêng.',
              text: 'Tìm theo từ khóa trong các tin đã duyệt, còn đang bán. Không công khai định danh người bán.',
            },
            {
              Icon: Fingerprint,
              title: 'Có trạng thái, có thể đối soát.',
              text: 'Lưu quyết định và kết quả delivery. Gửi không rõ kết quả cần BQL kiểm tra, không tự gửi lại.',
            },
          ].map(({ Icon, title, text }) => (
            <Reveal className="feature-row" key={title}>
              <span>
                <Icon size={25} strokeWidth={1.4} />
              </span>
              <div>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
              <ArrowUpRight size={17} />
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
