'use client';
import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowRight, Check, RefreshCw, Send, X } from 'lucide-react';
import type { Delivery } from '@/lib/contracts';
import { useData, mutate } from './use-data';
import { date, Empty, labels, Notice, Status, evidenceLabels } from './shared';
const partLabels: Record<string, string> = {
  post_text: 'Bài text',
  cover_photo_with_caption: 'Ảnh bìa kèm nội dung',
  additional_photo: 'Ảnh bổ sung',
  listing_code: 'Mã tin',
  sold_notice: 'Thông báo đã bán',
};
function ReconcileDialog({
  delivery,
  onClose,
  onSuccess,
}: {
  delivery: Delivery;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState('');
  const [decision, setDecision] = useState<'sent' | 'not_sent'>('not_sent');
  const [messageId, setMessageId] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const unknownPart = delivery.parts?.find((p) => p.status === 'unknown');
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  async function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!confirmed || !reason.trim() || busy) return;
    setBusy(true);
    setError('');
    try {
      await mutate(`deliveries/${delivery.id}/reconcile`, {
        decision,
        reason: reason.trim(),
        ...(decision === 'sent' && messageId.trim() ? { sent_message_id: messageId.trim() } : {}),
        ...(unknownPart ? { part_id: unknownPart.id } : {}),
      });
      onSuccess();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Chưa xác định kết quả. Làm mới trước khi thử lại.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      ref={ref}
      className="review-dialog"
      aria-labelledby="reconcile-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="dialog-heading">
        <span className="section-kicker">ĐỐI SOÁT THỦ CÔNG</span>
        <button
          className="icon-button"
          aria-label="Đóng đối soát"
          onClick={onClose}
          disabled={busy}
        >
          <X size={20} />
        </button>
      </div>
      <h2 id="reconcile-title">Xác minh kết quả gửi</h2>
      <p className="listing-code">Tin {delivery.listing_id}</p>
      {unknownPart && (
        <p className="field-help">
          Đối soát riêng phần <strong>{partLabels[unknownPart.kind]}</strong> (vị trí{' '}
          {unknownPart.position + 1}, ID {unknownPart.id}). Phần đã gửi không bị gửi lại; phần sau
          chỉ tiếp tục khi phần này được xác minh đã gửi.
        </p>
      )}
      <Notice message="Dừng publisher cũ và kiểm tra hội thoại nhóm trước khi quyết định. Không gửi lại khi chưa biết lần gửi trước có thành công hay không." />
      <form onSubmit={submit}>
        <label htmlFor="decision">Kết quả đã xác minh</label>
        <select
          id="decision"
          value={decision}
          onChange={(e) => setDecision(e.target.value as 'sent' | 'not_sent')}
        >
          <option value="not_sent">Chắc chắn chưa gửi → failed</option>
          <option value="sent">Đã xác minh gửi → sent</option>
        </select>
        {decision === 'sent' && (
          <>
            <label htmlFor="sent-id">
              {unknownPart ? 'ID tin nhắn của phần này *' : 'ID tin nhắn gửi (nếu có)'}
            </label>
            <input
              id="sent-id"
              value={messageId}
              onChange={(e) => setMessageId(e.target.value)}
              maxLength={200}
              required={!!unknownPart}
            />
          </>
        )}
        <label htmlFor="reconcile-reason">Lý do và bằng chứng đối soát *</label>
        <textarea
          id="reconcile-reason"
          required
          rows={3}
          maxLength={1000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Đã kiểm tra nhóm nào, thời điểm nào, kết quả ra sao…"
        />
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            required
          />
          <span>
            Tôi đã dừng publisher cũ và trực tiếp kiểm tra kết quả. ACK mock không được xem là bằng
            chứng Zalo thật.
          </span>
        </label>
        {error && <Notice message={error} />}
        <div className="dialog-actions">
          <button className="button button-white" type="button" onClick={onClose} disabled={busy}>
            Hủy
          </button>
          <button
            className="button button-navy"
            type="submit"
            disabled={busy || !confirmed || !reason.trim()}
          >
            {busy ? 'Đang lưu…' : 'Xác nhận đối soát'}
            <Check size={16} />
          </button>
        </div>
      </form>
    </dialog>
  );
}
export function DeliveryMonitor() {
  const { data, error, loading, refresh } = useData<Delivery[]>('deliveries');
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState<Delivery | null>(null);
  const [message, setMessage] = useState('');
  const rows = data?.filter((row) => filter === 'all' || row.status === filter) || [];
  return (
    <>
      <div className="page-title">
        <div>
          <span className="section-kicker">XUẤT BẢN CÓ KIỂM SOÁT</span>
          <h1>
            Theo dấu từng tin đăng<span className="gold-period">.</span>
          </h1>
          <p>Từ hàng chờ đến kết quả gửi, mọi trạng thái đều có thể kiểm tra.</p>
        </div>
        <button className="button button-white" onClick={refresh} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          Làm mới
        </button>
      </div>
      {message && <Notice success message={message} />}
      <div className="delivery-warning">
        <AlertTriangle size={21} />
        <div>
          <strong>Trạng thái backend không thay thế bằng chứng trên Zalo.</strong>
          <p>
            Connector Zalo thật chưa được xác minh. Delivery “unknown” cần đối soát; hệ thống không
            tự động gửi lại. Queued chỉ là hàng chờ; sent chỉ ghi nhận ACK, có thể là giả lập.
          </p>
        </div>
      </div>
      <section className="data-card table-card">
        <div className="table-toolbar">
          <div className="filter-tabs" aria-label="Lọc delivery">
            {['all', 'queued', 'claimed', 'sent', 'failed', 'unknown', 'cancelled'].map(
              (status) => (
                <button
                  className={filter === status ? 'selected' : ''}
                  key={status}
                  onClick={() => setFilter(status)}
                  aria-pressed={filter === status}
                >
                  {status === 'all' ? 'Tất cả' : labels[status]}
                </button>
              ),
            )}
          </div>
        </div>
        {error ? (
          <div className="table-message">
            <Notice message={error} />
          </div>
        ) : loading ? (
          <div className="skeleton-block" aria-label="Đang tải delivery" />
        ) : rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Tin đăng / Delivery</th>
                  <th>Nhóm đích</th>
                  <th>Trạng thái</th>
                  <th>Số lần</th>
                  <th>Cập nhật / Lỗi cuối</th>
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
                          <Send size={21} />
                        </span>
                        <span>
                          <strong>{row.listing_id}</strong>
                          <small className="delivery-code" title={row.id}>
                            {row.id}
                          </small>
                        </span>
                      </div>
                    </td>
                    <td className="group-cell">{row.target_group_id}</td>
                    <td>
                      <Status value={row.status} />
                      <p className="field-help">
                        {evidenceLabels[row.transport_mode || 'unverified']}
                      </p>
                      {row.sent_message_id && <small>ID: {row.sent_message_id}</small>}
                      {!!row.parts?.length && (
                        <details>
                          <summary>
                            {row.parts.filter((p) => p.status === 'sent').length}/{row.parts.length}{' '}
                            phần có receipt
                          </summary>
                          {row.parts.map((part) => (
                            <p className="field-help" key={part.id}>
                              <strong>{partLabels[part.kind] || part.kind}</strong> ·{' '}
                              {labels[part.status] || part.status}
                              <br />
                              ID phần: {part.id}
                              <br />
                              {part.sent_message_id && (
                                <>
                                  Receipt: {part.sent_message_id}
                                  <br />
                                </>
                              )}
                              {evidenceLabels[part.transport_mode] || part.transport_mode} ·{' '}
                              {part.attempts} lần
                              {part.last_error && (
                                <>
                                  <br />
                                  {part.last_error}
                                </>
                              )}
                            </p>
                          ))}
                        </details>
                      )}
                    </td>
                    <td>{row.attempts}</td>
                    <td className="date-cell">
                      {date(row.updated_at)}
                      {row.last_error && <small className="last-error">{row.last_error}</small>}
                    </td>
                    <td>
                      {row.status === 'unknown' ? (
                        <button className="row-action" onClick={() => setSelected(row)}>
                          Đối soát
                          <ArrowRight size={15} />
                        </button>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>
            Delivery xuất hiện khi một tin được duyệt với group và community đã cấu hình đúng.
          </Empty>
        )}
        <div className="table-footer">
          <span>{data ? `${rows.length} delivery đang hiển thị` : 'Chưa có dữ liệu'}</span>
          <span>Không có thao tác tự động retry</span>
        </div>
      </section>
      {selected && (
        <ReconcileDialog
          key={selected.id}
          delivery={selected}
          onClose={() => setSelected(null)}
          onSuccess={() => {
            setSelected(null);
            setMessage(
              'Đã lưu đối soát. Phần đã gửi không được gửi lại; phần tiếp theo chỉ tiếp tục khi đủ điều kiện.',
            );
            refresh();
          }}
        />
      )}
    </>
  );
}
