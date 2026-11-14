import type { Metadata } from 'next';
import '@fontsource/outfit/latin-400.css';
import '@fontsource/outfit/latin-500.css';
import '@fontsource/outfit/latin-600.css';
import '@fontsource/be-vietnam-pro/latin-400.css';
import '@fontsource/be-vietnam-pro/latin-500.css';
import '@fontsource/be-vietnam-pro/latin-600.css';
import '@fontsource/be-vietnam-pro/vietnamese-400.css';
import '@fontsource/be-vietnam-pro/vietnamese-500.css';
import '@fontsource/be-vietnam-pro/vietnamese-600.css';
import './globals.css';
import './landing.css';
export const metadata: Metadata = {
  icons: { icon: '/favicon.svg' },
  title: {
    default: 'NeighborMarket AI — Chợ cư dân thông minh',
    template: '%s · NeighborMarket AI',
  },
  description:
    'Trợ lý chợ cư dân với kiểm duyệt của Ban Quản lý. Dự án demo độc lập, kết nối Zalo thật chưa được xác minh.',
  robots: { index: false, follow: false },
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" data-type="software">
      <body>
        <a className="skip-link" href="#main">
          Bỏ qua điều hướng
        </a>
        {children}
      </body>
    </html>
  );
}
