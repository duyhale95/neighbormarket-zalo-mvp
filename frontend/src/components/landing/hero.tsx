import { ArrowDown, ArrowRight, Check, Sparkles } from 'lucide-react';
import { ArrowLink } from '@/components/brand';
export function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-heading">
      <div className="sunrise-ground" aria-hidden="true">
        <div className="sunrise-orb orb-one" />
        <div className="sunrise-orb orb-two" />
        <div className="sun-arc arc-one" />
        <div className="sun-arc arc-two" />
        <div className="sun-arc arc-three" />
      </div>
      <div className="hero-content">
        <span className="hero-pill">
          <Sparkles size={13} /> Một cộng đồng. Nhiều kết nối đáng tin.
        </span>
        <h1 id="hero-heading">
          Chợ cư dân thông minh,
          <br /> <span>an tâm</span> trong từng tin đăng.
        </h1>
        <p>
          Đăng bán, tìm mua ngay trong cuộc trò chuyện quen thuộc.
          <br className="desktop-break" /> NeighborMarket AI hỗ trợ kiểm duyệt, để Ban Quản lý
          <br className="desktop-break" /> gìn giữ một cộng đồng minh bạch hơn.
        </p>
        <div className="hero-actions">
          <ArrowLink href="#quy-trinh" className="button-navy">
            Khám phá quy trình
          </ArrowLink>
          <a href="/bql" className="button button-ghost">
            Xem BQL Dashboard
            <ArrowRight size={17} />
          </a>
        </div>
        <div className="hero-assurance">
          <span>
            <Check size={13} /> BQL duyệt trước khi công khai
          </span>
          <i />
          <span>
            <Check size={13} /> Dữ liệu và trạng thái có thể truy vết
          </span>
        </div>
        <span className="hero-editorial">
          AI-powered community marketplace · Human-in-the-loop moderation
        </span>
      </div>
      <div className="hero-bottom">
        <span>01 — KẾT NỐI BẮT ĐẦU TỪ SỰ TIN TƯỞNG</span>
        <a href="#giai-phap" aria-label="Cuộn đến giải pháp">
          <ArrowDown size={18} />
        </a>
        <span>MVP DEMO · LIVE ZALO CHƯA XÁC MINH</span>
      </div>
    </section>
  );
}
