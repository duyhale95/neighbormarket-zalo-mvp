'use client';
import { useRef } from 'react';
import {
  Armchair,
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  MessageCircle,
  Search,
  ShieldAlert,
} from 'lucide-react';
const scenarios = [
  {
    Icon: Armchair,
    stage: '01 / NGƯỜI BÁN',
    title: 'Một chiếc ghế, một chủ mới.',
    text: 'Cư dân gửi thông tin món đồ còn tốt vào cuộc trò chuyện riêng.',
  },
  {
    Icon: Search,
    stage: '02 / NGƯỜI MUA',
    title: 'Tìm món đồ mình cần.',
    text: 'Nhắn từ khóa “máy giặt” để tìm tin đã duyệt còn đang bán.',
  },
  {
    Icon: ShieldAlert,
    stage: '03 / AI HỖ TRỢ',
    title: 'Chậm một nhịp, an tâm hơn.',
    text: 'Nội dung thiếu hoặc có dấu hiệu nhạy cảm được đề nghị kiểm tra.',
  },
  {
    Icon: BadgeCheck,
    stage: '04 / BQL QUYẾT ĐỊNH',
    title: 'Một lần duyệt có trách nhiệm.',
    text: 'Ban Quản lý kiểm tra và ghi lý do trước khi công khai.',
  },
  {
    Icon: MessageCircle,
    stage: '05 / NHÓM LEGIT',
    title: 'Đúng tin. Đúng nơi.',
    text: 'Tin đã duyệt vào hàng chờ nhóm được phép. Luồng gửi thật đang chờ xác minh.',
  },
];
export function Scenarios() {
  const track = useRef<HTMLDivElement>(null);
  return (
    <section className="scenarios section-wrap" id="giai-phap">
      <div className="section-header inline-header">
        <div>
          <span className="section-kicker">NHỮNG CHUYỆN NHỎ, KẾT NỐI LỚN</span>
          <h2>
            Cuộc sống có thêm
            <br />
            một chút thuận tiện.
          </h2>
        </div>
        <div className="scenario-controls">
          <button
            aria-label="Tình huống trước"
            onClick={() => track.current?.scrollBy({ left: -320, behavior: 'smooth' })}
          >
            <ArrowLeft size={19} />
          </button>
          <button
            aria-label="Tình huống tiếp"
            onClick={() => track.current?.scrollBy({ left: 320, behavior: 'smooth' })}
          >
            <ArrowRight size={19} />
          </button>
        </div>
      </div>
      <div
        ref={track}
        className="scenario-track"
        tabIndex={0}
        role="region"
        aria-label="Các tình huống sử dụng, vuốt hoặc dùng phím mũi tên"
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
            e.preventDefault();
            track.current?.scrollBy({
              left: e.key === 'ArrowRight' ? 320 : -320,
              behavior: 'smooth',
            });
          }
        }}
      >
        {scenarios.map(({ Icon, stage, title, text }) => (
          <article className="scenario-card" key={stage}>
            <div className="scenario-top">
              <span>
                <Icon size={22} strokeWidth={1.5} />
              </span>
              <small>{stage}</small>
            </div>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
      <div className="section-divider">
        <span>ĐƯỢC THIẾT KẾ CHO CƯ DÂN. ĐƯỢC KIỂM SOÁT BỞI CON NGƯỜI.</span>
        <i />
      </div>
    </section>
  );
}
