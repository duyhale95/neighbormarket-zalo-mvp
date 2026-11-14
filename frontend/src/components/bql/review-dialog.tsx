'use client';
import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowLeft, Check, X } from 'lucide-react';
import { flagsOf, type Listing } from '@/lib/contracts';
import { flagLabels, money, date, Notice, Status, sourceLabels, riskLabels } from './shared';
import { mutate } from './use-data';
import { ImageReview } from './image-review';
import styles from './review.module.css';
export function ReviewDialog({
  listing: initialListing,
  onClose,
  onSuccess,
}: {
  listing: Listing;
  onClose: () => void;
  onSuccess: (message: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [listing, setListing] = useState(initialListing);
  const [manualImageReview, setManualImageReview] = useState(false);
  const [reason, setReason] = useState('');
  const [action, setAction] = useState<'approve' | 'reject' | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const flags = flagsOf(listing.moderation_flags);
  const blocked = flags.some((flag) => ['sensitive_information', 'prohibited'].includes(flag));
  const photoPending = listing.images?.some((i) => i.status === 'pending');
  const photoNeedsReview = listing.images?.some((i) => i.status !== 'clear');
  async function confirm() {
    if (!action || !reason.trim() || busy) return;
    setBusy(true);
    setError('');
    try {
      const result = await mutate(`listings/${listing.id}/review`, {
        action,
        reason: reason.trim(),
        ...(listing.images?.length
          ? {
              image_review_token: listing.image_review_token,
              manual_image_review: manualImageReview,
            }
          : {}),
      });
      onSuccess(
        result.delivery_status === 'not_configured'
          ? 'Đã duyệt. Hãy kiểm tra cấu hình nhóm để đăng tin.'
          : action === 'approve'
            ? 'Đã duyệt và xếp hàng đăng nhóm.'
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
      className={`review-dialog ${styles.dialog}`}
      aria-labelledby="review-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      <header className={styles.header}>
        <div>
          <p className={styles.code}>{listing.id}</p>
          <h2 id="review-title">
            {action
              ? action === 'approve'
                ? 'Xác nhận phê duyệt'
                : 'Xác nhận từ chối'
              : listing.title}
          </h2>
        </div>
        <button
          className="icon-button"
          aria-label="Đóng chi tiết"
          onClick={onClose}
          disabled={busy}
        >
          <X size={20} />
        </button>
      </header>
      <div className={styles.body}>
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
                ? 'Tin sẽ vào hàng chờ đăng nhóm Zalo đã cấu hình.'
                : 'Người bán có thể xem lý do bằng mã tin.'}
            </p>
          </>
        ) : (
          <div className={styles.columns}>
            <section className={styles.item} aria-label="Thông tin tin đăng">
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
              </dl>
              <ImageReview
                listing={listing}
                onChange={(next) => {
                  setListing(next);
                  setManualImageReview(false);
                  setAction(null);
                }}
              />
            </section>
            <section className={styles.review} aria-label="Kiểm duyệt và quyết định">
              <h3>Kiểm duyệt và quyết định</h3>
              {listing.moderation ? (
                <div className="moderation-alert">
                  <AlertTriangle size={20} aria-hidden="true" />
                  <div>
                    <strong>{riskLabels[listing.moderation.risk_level]}</strong>
                    <span>{listing.moderation.reason}</span>
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
              {listing.moderation?.omni && (
                <div className="moderation-alert">
                  <AlertTriangle size={20} aria-hidden="true" />
                  <div>
                    <strong>Nhãn nội dung từ OpenAI</strong>
                    <span>
                      {listing.moderation.omni.status === 'flagged'
                        ? listing.moderation.omni.categories.join(', ') || 'Cần xem xét nội dung'
                        : listing.moderation.omni.status === 'clear'
                          ? 'Không có nhãn bị gắn cờ'
                          : 'Chưa có kết quả kiểm tra tự động'}
                    </span>
                    <small>{listing.moderation.omni.model}</small>
                  </div>
                </div>
              )}
              {blocked && <Notice message="Tin bị chặn duyệt. Ghi rõ lý do để người bán sửa." />}
              {photoNeedsReview && !photoPending && listing.status === 'pending' && (
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={manualImageReview}
                    onChange={(e) => setManualImageReview(e.target.checked)}
                  />
                  <span>Tôi đã kiểm tra ảnh và ghi nhận kết quả trong lý do.</span>
                </label>
              )}
              {photoPending && (
                <Notice message="Ảnh đang được kiểm tra. Hãy làm mới trước khi duyệt." />
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
            </section>
          </div>
        )}
        {error && <Notice message={error} />}
      </div>
      <div className={`dialog-actions ${styles.actions}`}>
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
              disabled={
                !reason.trim() ||
                blocked ||
                photoPending ||
                (!!photoNeedsReview && !manualImageReview)
              }
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
