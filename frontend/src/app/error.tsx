'use client';
import Link from 'next/link';
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main id="main" className="route-error">
      <h1>Trang chưa tải được.</h1>
      <p>
        Kiểm tra kết nối và thử tải lại. Nếu đang duyệt tin, xem trạng thái trước khi gửi lại quyết
        định.
      </p>
      <button className="button button-navy" onClick={reset}>
        Thử tải lại
      </button>
      <Link href="/">Về trang chủ</Link>
    </main>
  );
}
