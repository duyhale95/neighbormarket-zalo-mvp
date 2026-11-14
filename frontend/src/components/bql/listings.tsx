'use client';
import { useMemo, useState } from 'react';
import { AlertTriangle, ArrowUpRight, Package, RefreshCw, Search } from 'lucide-react';
import { flagsOf, type Listing } from '@/lib/contracts';
import { useData } from './use-data';
import { Empty, money, date, Notice, Status, labels, sourceLabels } from './shared';
import { ReviewDialog } from './review-dialog';
export function ListingQueue() {
  const { data, error, loading, refresh } = useData<Listing[]>('listings');
  const [filter, setFilter] = useState('pending');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Listing | null>(null);
  const [message, setMessage] = useState('');
  const rows = useMemo(
    () =>
      data?.filter(
        (row) =>
          (filter === 'all' || row.status === filter) &&
          `${row.title} ${row.id}`.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi')),
      ) || [],
    [data, filter, search],
  );
  return (
    <>
      <div className="page-title">
        <div>
          <span className="section-kicker">KIỂM DUYỆT NỘI DUNG</span>
          <h1>
            Những tin đăng đáng tin<span className="gold-period">.</span>
          </h1>
          <p>Xem kỹ nội dung. Giữ quyền quyết định trong tay Ban Quản lý.</p>
        </div>
        <button className="button button-white" onClick={refresh} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          Làm mới
        </button>
      </div>
      {message && <Notice success message={message} />}
      <div className="review-info">
        <span className="info-icon">
          <AlertTriangle size={18} />
        </span>
        <p>
          AI chỉ gợi ý kiểm duyệt. Hãy kiểm tra thông tin cá nhân, nội dung và tình trạng sản phẩm
          trước khi duyệt.
        </p>
      </div>
      <section className="data-card table-card">
        <div className="table-toolbar">
          <div className="filter-tabs" aria-label="Lọc trạng thái">
            {['pending', 'approved', 'rejected', 'sold', 'all'].map((value) => (
              <button
                key={value}
                className={filter === value ? 'selected' : ''}
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {value === 'all' ? 'Tất cả' : labels[value]}
                {value === 'pending' && data && (
                  <span>{data.filter((r) => r.status === 'pending').length}</span>
                )}
              </button>
            ))}
          </div>
          <label className="search-field">
            <Search size={17} />
            <span className="sr-only">Tìm theo tên hoặc mã tin</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tên sản phẩm, mã tin…"
            />
          </label>
        </div>
        {error ? (
          <div className="table-message">
            <Notice message={error} />
          </div>
        ) : loading ? (
          <div className="skeleton-block" aria-label="Đang tải danh sách" />
        ) : rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Sản phẩm / Mã tin</th>
                  <th>Giá bán</th>
                  <th>Trạng thái</th>
                  <th>Kiểm duyệt</th>
                  <th>Ngày tạo</th>
                  <th>
                    <span className="sr-only">Thao tác</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <div className="table-product">
                        <span className="item-icon">
                          <Package size={22} />
                        </span>
                        <span>
                          <strong>{row.title}</strong>
                          <small>{row.id}</small>
                          <small>{sourceLabels[row.source_channel || 'legacy']}</small>
                        </span>
                      </div>
                    </td>
                    <td className="price-cell">{money(row.price_vnd)}</td>
                    <td>
                      <Status value={row.status} />
                    </td>
                    <td>
                      {flagsOf(row.moderation_flags).length ? (
                        <span className="flag-count">
                          <AlertTriangle size={14} />
                          {flagsOf(row.moderation_flags).length} cờ cần xem
                        </span>
                      ) : (
                        <span className="muted">Chưa có cờ</span>
                      )}
                    </td>
                    <td className="date-cell">{date(row.created_at)}</td>
                    <td>
                      <button
                        className="row-action"
                        aria-label={`Xem ${row.title}`}
                        onClick={() => setSelected(row)}
                      >
                        Xem tin
                        <ArrowUpRight size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>
            Không có tin phù hợp với bộ lọc. Tin mới sẽ xuất hiện sau khi cư dân xác nhận bản nháp.
          </Empty>
        )}
        <div className="table-footer">
          <span>{data ? `${rows.length} tin đang hiển thị` : 'Chưa có dữ liệu'}</span>
          <span>API trả tối đa 100 tin gần nhất</span>
        </div>
      </section>
      {selected && (
        <ReviewDialog
          key={selected.id}
          listing={selected}
          onClose={() => setSelected(null)}
          onSuccess={(text) => {
            setSelected(null);
            setMessage(text);
            refresh();
          }}
        />
      )}
    </>
  );
}
