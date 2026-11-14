import { ArrowUpRight, Quote } from 'lucide-react';
import { ArrowLink, ProjectMark, VinhomesLogo } from '@/components/brand';
import { Reveal } from './reveal';
export function Community() {
  return (
    <section className="community-section section-wrap">
      <Reveal>
        <div className="section-header centered">
          <span className="section-kicker">BẮT ĐẦU TỪ NHỮNG ĐIỀU RẤT ĐỜI THƯỜNG</span>
          <h2>
            Đồ cũ có một hành trình mới.
            <br />
            Cộng đồng có thêm sự gắn kết.
          </h2>
          <p>Hai tình huống sản phẩm — không phải đánh giá từ cư dân thực tế.</p>
        </div>
      </Reveal>
      <div className="story-notes">
        <Reveal className="story-note note-resident">
          <Quote size={26} strokeWidth={1} />
          <blockquote>
            “Mình có chiếc ghế còn tốt, nhưng không muốn tin đăng trôi giữa hàng trăm tin nhắn.”
          </blockquote>
          <div>
            <span className="story-initial">C</span>
            <span>
              <strong>Góc nhìn cư dân</strong>
              <small>Tình huống minh họa</small>
            </span>
            <span className="handwritten">a new beginning</span>
          </div>
        </Reveal>
        <Reveal className="story-note note-admin">
          <Quote size={26} strokeWidth={1} />
          <blockquote>
            “BQL cần kiểm soát nội dung trước khi đăng vào nhóm chung, để mỗi kết nối có thêm sự tin
            tưởng.”
          </blockquote>
          <div>
            <span className="story-initial">B</span>
            <span>
              <strong>Góc nhìn Ban Quản lý</strong>
              <small>Tình huống minh họa</small>
            </span>
            <span className="handwritten">a little more trust</span>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
export function FinalCTA() {
  return (
    <section className="final-cta">
      <div className="cta-sun" aria-hidden="true" />
      <div className="section-wrap">
        <Reveal>
          <span className="section-kicker">KẾT NỐI TỐT HƠN, SỐNG AN TÂM HƠN</span>
          <h2>
            Một cộng đồng văn minh
            <br /> bắt đầu từ những kết nối
            <br /> <span>đáng tin cậy.</span>
          </h2>
          <p>
            Trợ lý hội thoại, kiểm duyệt và quản trị — cùng tạo nên
            <br className="desktop-break" /> một trải nghiệm mua bán thuận tiện hơn cho cư dân.
          </p>
          <div className="hero-actions">
            <ArrowLink href="#quy-trinh" className="button-navy">
              Khám phá workflow
            </ArrowLink>
            <ArrowLink href="/bql" className="button-ghost">
              Truy cập BQL Demo
            </ArrowLink>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
export function Footer() {
  return (
    <footer className="landing-footer section-wrap">
      <div className="footer-top">
        <div>
          <ProjectMark />
          <p>
            Công nghệ kết nối.
            <br />
            Con người tạo niềm tin.
          </p>
        </div>
        <div className="footer-links">
          <a href="#quy-trinh">
            Quy trình
            <ArrowUpRight size={14} />
          </a>
          <a href="/bql">
            Không gian BQL
            <ArrowUpRight size={14} />
          </a>
          <a
            href="https://github.com/duyhale95/neighbormarket-zalo-mvp"
            target="_blank"
            rel="noreferrer"
          >
            GitHub repository
            <ArrowUpRight size={14} />
          </a>
          <span>Next.js · FastAPI · SQLite</span>
        </div>
        <div className="footer-brand">
          <VinhomesLogo />
          <p>
            Nhận diện dùng trong bản concept.
            <br />
            Không liên kết hoặc bảo trợ chính thức.
          </p>
        </div>
      </div>
      <div className="footer-bottom">
        <span>© {new Date().getFullYear()} NeighborMarket AI · Independent demo</span>
        <span>Dự án độc lập. Không phải sản phẩm chính thức của Vinhomes, Zalo hay VinAI.</span>
      </div>
    </footer>
  );
}
