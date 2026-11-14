'use client';
import Link from 'next/link';
import {
  ArrowRight,
  ArrowUpRight,
  CheckCheck,
  CircleCheck,
  Clock3,
  FileText,
  Package,
  RefreshCw,
  Send,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { useData } from './use-data';
import { Empty, money, Notice, Status } from './shared';
import type { Listing, Stats, Delivery } from '@/lib/contracts';
const metrics = [
  { key: 'total', label: 'Tổng tin đăng', Icon: FileText },
  { key: 'pending', label: 'Chờ kiểm duyệt', Icon: Clock3 },
  { key: 'approved', label: 'Đã phê duyệt', Icon: CircleCheck },
  { key: 'rejected', label: 'Đã từ chối', Icon: XCircle },
  { key: 'sold', label: 'Đã bán', Icon: CheckCheck },
  { key: 'sent', label: 'Đã ghi nhận gửi', Icon: Send },
] as const;
export function Overview() {
  const stats = useData<Stats>('stats');
  const listings = useData<Listing[]>('listings');
  const deliveries = useData<Delivery[]>('deliveries');
  const health = useData<{ status: string; community: string }>('health');
  const loading = stats.loading || listings.loading || deliveries.loading || health.loading;
  const error = stats.error || listings.error || deliveries.error || health.error;
  const refresh = () => {
    stats.refresh();
    listings.refresh();
    deliveries.refresh();
    health.refresh();
  };
  const pending = listings.data?.filter((row) => row.status === 'pending') || [];
  return (
    <>
      <div className="page-title">
        <div>
          <span className="section-kicker">KHÔNG GIAN ĐIỀU HÀNH</span>
          <h1>
            Tổng quan cộng đồng<span className="gold-period">.</span>
          </h1>
          <p>Mỗi tin đăng được kiểm soát. Mỗi kết nối thêm an tâm.</p>
        </div>
        <button className="button button-white" onClick={refresh} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          Làm mới
        </button>
      </div>
      <div className="connection-row">
        <span className={`connection ${!error && health.data?.status === 'ok' ? 'online' : ''}`}>
          <i />
          {loading
            ? 'Đang kiểm tra kết nối…'
            : error
              ? 'Backend chưa kết nối'
              : 'Đã kết nối FastAPI'}
        </span>
        <span>Cộng đồng: {health.data?.community || '—'} · Dữ liệu từ backend</span>
      </div>
      {error && <Notice message={error} />}
      <div className="metric-grid">
        {metrics.map(({ key, label, Icon }) => (
          <article
            className={`metric-card ${key === 'pending' ? 'metric-featured' : ''}`}
            key={key}
          >
            <div>
              <span>{label}</span>
              <Icon size={19} />
            </div>
            <strong>{loading ? '…' : stats.data ? stats.data[key] : '—'}</strong>
            <small>
              {key === 'pending'
                ? 'Cần quyết định của BQL'
                : key === 'sent'
                  ? 'Theo ACK được lưu trong backend'
                  : 'Trạng thái hiện tại'}
            </small>
          </article>
        ))}
      </div>
      <div className="overview-grid">
        <section className="data-card">
          <div className="card-heading">
            <div>
              <span className="mini-kicker">HÀNG ĐỢI</span>
              <h2>Tin cần bạn xem</h2>
            </div>
            <Link href="/bql/listings" className="text-link">
              Xem tất cả
              <ArrowUpRight size={16} />
            </Link>
          </div>
          {listings.loading ? (
            <div className="skeleton-block" aria-label="Đang tải tin đăng" />
          ) : pending.length ? (
            <div className="queue-list">
              {pending.slice(0, 4).map((row) => (
                <Link href="/bql/listings" className="queue-item" key={row.id}>
                  <span className="item-icon">
                    <Package size={23} />
                  </span>
                  <span>
                    <strong>{row.title}</strong>
                    <small>
                      {row.id} · {money(row.price_vnd)}
                    </small>
                  </span>
                  <Status value={row.status} />
                  <ArrowRight size={16} />
                </Link>
              ))}
            </div>
          ) : (
            <Empty>
              {listings.error
                ? 'Kết nối backend để xem hàng đợi.'
                : 'Các tin chờ duyệt sẽ xuất hiện tại đây.'}
            </Empty>
          )}
        </section>
        <aside className="guidance-card">
          <span className="guidance-icon">
            <ShieldCheck size={26} />
          </span>
          <span className="mini-kicker">NGUYÊN TẮC VẬN HÀNH</span>
          <h2>
            AI gợi ý.
            <br />
            BQL quyết định.
          </h2>
          <p>
            Kiểm tra nội dung, thông tin nhạy cảm và lý do trước khi phê duyệt. Tin chưa duyệt sẽ
            không vào hàng chờ xuất bản.
          </p>
          <Link href="/bql/listings" className="text-link">
            Mở hàng đợi kiểm duyệt
            <ArrowRight size={16} />
          </Link>
        </aside>
      </div>
      <section className="data-card delivery-summary">
        <div className="card-heading">
          <div>
            <span className="mini-kicker">THEO DÕI XUẤT BẢN</span>
            <h2>Từ phê duyệt đến nhóm Legit</h2>
          </div>
          <Link href="/bql/deliveries" className="text-link">
            Xem delivery
            <ArrowUpRight size={16} />
          </Link>
        </div>
        <div className="delivery-progress">
          {['queued', 'claimed', 'sent', 'unknown'].map((status) => (
            <div key={status}>
              <Status value={status} />
              <strong>
                {deliveries.data ? deliveries.data.filter((d) => d.status === status).length : '—'}
              </strong>
            </div>
          ))}
        </div>
        <p className="data-footnote">
          “Đã ghi nhận gửi” phản ánh ACK trong backend. ACK mô phỏng không xác nhận có tin nhắn Zalo
          thật.
        </p>
      </section>
    </>
  );
}
