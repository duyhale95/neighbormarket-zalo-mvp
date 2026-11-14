'use client';
import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowLeft, Check, X } from 'lucide-react';
import { flagsOf, type Listing } from '@/lib/contracts';
import { flagLabels, money, date, Notice, Status, sourceLabels, riskLabels } from './shared';
import { mutate } from './use-data';
export function ReviewDialog({
  listing,
  onClose,
  onSuccess,
}: {
  listing: Listing;
  onClose: () => void;
  onSuccess: (message: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState('');
  const [action, setAction] = useState<'approve' | 'reject' | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const flags = flagsOf(listing.moderation_flags);
  const blocked = flags.some((flag) => ['sensitive_information', 'prohibited'].includes(flag));
  async function confirm() {
    if (!action || !reason.trim() || busy) return;
    setBusy(true);
    setError('');
    try {
      const result = await mutate(`listings/${listing.id}/review`, {
        action,
        reason: reason.trim(),
      });
      onSuccess(
        result.delivery_status === 'not_configured'
          ? 'Đã duyệt nhưng chưa tạo delivery: thiếu cấu hình nhóm hoặc community không khớp. Không có backfill tự động.'
          : action === 'approve'
            ? 'Đã duyệt tin và tạo delivery trong hàng chờ.'
            : 'Đã từ chối tin đăng.',
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chưa xác định kết quả. Hãy làm mới danh sách.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      ref={dialog}
      className="review-dialog"
      aria-labelledby="review-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="dialog-heading">
        <span className="section-kicker">
          {action ? 'XÁC NHẬN QUYẾT ĐỊNH' : 'CHI TIẾT TIN ĐĂNG'}
        </span>
        <button
          className="icon-button"
          aria-label="Đóng chi tiết"
          onClick={onClose}
          disabled={busy}
        >
          <X size={20} />
        </button>
      </div>
      <h2 id="review-title">
        {action
          ? action === 'approve'
            ? 'Phê duyệt tin đăng này?'
            : 'Từ chối tin đăng này?'
          : listing.title}
      </h2>
      <p className="listing-code">{listing.id}</p>
      {action ? (
        <>
          <div className="confirmation-summary">
            <strong>{listing.title}</strong>
            <p>
              {money(listing.price_vnd)} · {listing.condition}
            </p>
            <small>Lý do: {reason}</small>
          </div>
          <p className="dialog-copy">
            {action === 'approve'
              ? 'Backend sẽ kiểm tra trạng thái và tạo delivery nếu nhóm đã cấu hình. Việc duyệt chưa đồng nghĩa với tin đã xuất hiện trên Zalo.'
              : 'Tin bị từ chối sẽ không được đưa vào hàng chờ xuất bản.'}
          </p>
        </>
      ) : (
        <>
          <div className="detail-price">
            {money(listing.price_vnd)}
            <Status value={listing.status} />
          </div>
          <dl className="details-list">
            <div>
              <dt>Tình trạng sản phẩm</dt>
              <dd>{listing.condition}</dd>
            </div>
            <div>
              <dt>Người đăng</dt>
              <dd>{listing.seller_id}</dd>
            </div>
            <div>
              <dt>Ngày tạo</dt>
              <dd>{date(listing.created_at)}</dd>
            </div>
            <div>
              <dt>Nguồn tin</dt>
              <dd>{sourceLabels[listing.source_channel || 'legacy']}</dd>
            </div>
            <div>
              <dt>Kết nối Zalo thật</dt>
              <dd>Chưa xác minh · nguồn tin không phải bằng chứng kết nối live</dd>
            </div>
          </dl>
          {listing.moderation ? (
            <div className="moderation-alert">
              <AlertTriangle size={20} aria-hidden="true" />
              <div>
                <strong>{riskLabels[listing.moderation.risk_level]}</strong>
                <span>{listing.moderation.reason}</span>
                <span>Luôn cần BQL duyệt · không có xác suất rủi ro đã hiệu chỉnh.</span>
                <small>
                  {listing.moderation.policy_version} · {listing.moderation.model_version} ·{' '}
                  {listing.moderation.ai_status === 'advisory'
                    ? 'Tín hiệu AI tư vấn'
                    : listing.moderation.ai_status === 'unavailable'
                      ? 'AI không khả dụng'
                      : 'Kiểm tra bằng luật'}
                </small>
              </div>
            </div>
          ) : (
            <p className="field-help">
              Tin cũ chưa có báo cáo moderation; BQL cần kiểm tra thủ công.
            </p>
          )}
          {flags.length > 0 && (
            <div className="moderation-alert">
              <AlertTriangle size={20} />
              <div>
                <strong>Cần BQL kiểm tra</strong>
                {flags.map((flag) => (
                  <span key={flag}>{flagLabels[flag] || flag}</span>
                ))}
              </div>
            </div>
          )}
          {blocked && (
            <Notice message="Có thông tin nhạy cảm hoặc từ khóa hàng cấm. Hãy từ chối và yêu cầu người bán viết lại; backend sẽ chặn phê duyệt." />
          )}
          {listing.status === 'pending' && (
            <>
              <label htmlFor="review-reason">
                Lý do quyết định <span aria-hidden="true">*</span>
              </label>
              <textarea
                id="review-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={1000}
                placeholder="Ghi nhận nội dung đã kiểm tra hoặc lý do từ chối…"
                required
                rows={3}
              />
              <p className="field-help">Bắt buộc · Tối đa 1.000 ký tự</p>
            </>
          )}
        </>
      )}
      {error && <Notice message={error} />}
      <div className="dialog-actions">
        {action ? (
          <>
            <button
              className="button button-white"
              onClick={() => {
                setAction(null);
                setError('');
              }}
              disabled={busy}
            >
              <ArrowLeft size={16} />
              Quay lại
            </button>
            <button
              className={`button ${action === 'approve' ? 'button-navy' : 'button-danger'}`}
              onClick={confirm}
              disabled={busy}
            >
              {busy
                ? 'Đang lưu…'
                : action === 'approve'
                  ? 'Xác nhận phê duyệt'
                  : 'Xác nhận từ chối'}
              <Check size={17} />
            </button>
          </>
        ) : listing.status === 'pending' ? (
          <>
            <button
              className="button button-white danger-text"
              onClick={() => setAction('reject')}
              disabled={!reason.trim()}
            >
              Từ chối tin
              <X size={17} />
            </button>
            <button
              className="button button-navy"
              onClick={() => setAction('approve')}
              disabled={!reason.trim() || blocked}
            >
              Phê duyệt tin
              <Check size={17} />
            </button>
          </>
        ) : (
          <button className="button button-white" onClick={onClose}>
            Đóng
          </button>
        )}
      </div>
    </dialog>
  );
}
