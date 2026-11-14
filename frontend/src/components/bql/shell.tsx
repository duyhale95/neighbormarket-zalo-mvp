'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Activity,
  ArrowUpRight,
  Bell,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  PackageCheck,
  PanelLeftClose,
  Radio,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { ProjectMark } from '@/components/brand';
const links = [
  { href: '/bql', label: 'Tổng quan', Icon: LayoutDashboard },
  { href: '/bql/listings', label: 'Kiểm duyệt tin', Icon: ShieldCheck },
  { href: '/bql/deliveries', label: 'Xuất bản nhóm', Icon: PackageCheck },
];
export function ConsoleShell({
  children,
  community,
}: {
  children: React.ReactNode;
  community: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  async function logout() {
    const r = await fetch('/api/auth/logout', { method: 'POST' });
    if (r.ok) {
      router.replace('/bql/login');
      router.refresh();
    }
  }
  return (
    <div className="console">
      <aside className="sidebar">
        <Link href="/" className="sidebar-brand" aria-label="NeighborMarket AI, về trang chủ">
          <ProjectMark compact />
        </Link>
        <div className="workspace-label">KHÔNG GIAN QUẢN TRỊ</div>
        <div className="community-switch">
          <span className="community-avatar">N</span>
          <div>
            <strong>Cộng đồng cư dân</strong>
            <small>{community} · Môi trường demo</small>
          </div>
          <ChevronRight size={16} />
        </div>
        <nav aria-label="Quản trị BQL">
          {links.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname === href ? 'page' : undefined}
              className={pathname === href ? 'active' : ''}
            >
              <Icon size={19} />
              {label}
              {pathname === href && <span className="active-dot" />}
            </Link>
          ))}
          <div className="nav-divider" />
          <p className="workspace-label">SẮP RA MẮT</p>
          {[
            { Icon: Radio, label: 'Giám sát cộng đồng' },
            { Icon: Bell, label: 'Cảnh báo cư dân' },
            { Icon: Activity, label: 'MLOps' },
          ].map(({ Icon, label }) => (
            <div className="future-nav" key={label}>
              <Icon size={18} />
              <span>
                {label}
                <small>Đang phát triển</small>
              </span>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-tip">
            <Sparkles size={20} />
            <strong>Con người quyết định.</strong>
            <p>AI hỗ trợ kiểm tra. Mọi tin đều cần BQL phê duyệt.</p>
          </div>
          <Link className="back-site" href="/">
            Xem trang giới thiệu
            <ArrowUpRight size={16} />
          </Link>
        </div>
      </aside>
      <div className="console-body">
        <header className="console-top">
          <div>
            <span className="top-location">NeighborMarket AI</span>
            <ChevronRight size={14} />
            <span>Ban Quản lý</span>
          </div>
          <div>
            <span className="demo-chip">DEMO ĐỘC LẬP</span>
            <button className="icon-button" onClick={logout} aria-label="Đăng xuất">
              <LogOut size={18} />
            </button>
            <span className="admin-avatar">BQ</span>
          </div>
        </header>
        <main id="main" className="console-main">
          {children}
        </main>
        <footer className="console-footer">
          <span>NeighborMarket AI · BQL Demo</span>
          <span>Connector Zalo thật chưa được xác minh</span>
        </footer>
      </div>
      <span className="sr-only">
        <PanelLeftClose /> Điều hướng khả dụng trên thiết bị di động
      </span>
    </div>
  );
}
