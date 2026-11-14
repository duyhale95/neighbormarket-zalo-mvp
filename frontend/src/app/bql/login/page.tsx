import Link from 'next/link';
import Image from 'next/image';
import { redirect } from 'next/navigation';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { getConfig, hasAccess } from '@/lib/auth';
import { VinhomesLogo, ProjectMark } from '@/components/brand';
import { LoginForm } from '@/components/bql/login-form';
export const dynamic = 'force-dynamic';
export const metadata = { title: 'Đăng nhập BQL' };
export default async function LoginPage() {
  if (await hasAccess()) redirect('/bql');
  let setupError = '';
  try {
    getConfig();
  } catch (e) {
    setupError = e instanceof Error ? e.message : 'Thiếu cấu hình máy chủ.';
  }
  return (
    <main id="main" className="login-page">
      <div className="login-story">
        <Link href="/" aria-label="Về trang chủ">
          <ProjectMark />
        </Link>
        <Image
          src="/brand/vinhomes-symbol.png"
          alt=""
          aria-hidden="true"
          width={1200}
          height={1200}
          className="login-bird"
          unoptimized
        />
        <div className="login-story-copy">
          <span className="eyebrow">DÀNH CHO BAN QUẢN LÝ</span>
          <h1>
            Mỗi tin đăng.
            <br />
            Một sự an tâm.
          </h1>
          <p>Một không gian để kiểm duyệt, theo dõi và chăm sóc những kết nối trong cộng đồng.</p>
          <div className="login-seal">
            <ShieldCheck size={26} />
            <div>
              <strong>Quyết định cuối cùng luôn thuộc về BQL.</strong>
              <span>AI hỗ trợ. Con người kiểm soát.</span>
            </div>
          </div>
        </div>
        <div className="login-story-footer">
          <VinhomesLogo />
          <span>
            Dự án demo độc lập
            <br />
            Không có liên kết hoặc bảo trợ chính thức.
          </span>
        </div>
      </div>
      <section className="login-card-wrap">
        <Link href="/" className="back-link">
          <ArrowLeft size={16} />
          Về trang giới thiệu
        </Link>
        <div className="login-card">
          <span className="section-kicker">NEIGHBORMARKET AI</span>
          <h2>Chào Ban Quản lý.</h2>
          <p className="login-intro">Đăng nhập để xem dữ liệu và quản lý tin đăng của cộng đồng.</p>
          <LoginForm setupError={setupError} />
        </div>
        <p className="login-bottom">Không gian demo · Không sử dụng dữ liệu cư dân nhạy cảm.</p>
      </section>
    </main>
  );
}
