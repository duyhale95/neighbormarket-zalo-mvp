'use client';
import Image from 'next/image';
import { useState } from 'react';
import type { Listing } from '@/lib/contracts';
import { mutate } from './use-data';
import { Notice } from './shared';
import styles from './media.module.css';

const states: Record<string, string> = {
  clear: 'Chưa bị gắn cờ',
  flagged: 'Cần xem nội dung',
  pending: 'Đang kiểm tra',
  error: 'Kiểm tra lỗi',
  unavailable: 'Chưa kiểm tra tự động',
  stale: 'Nội dung đã thay đổi',
};

export function ImageReview({
  listing,
  onChange,
}: {
  listing: Listing;
  onChange: (next: Listing) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [view, setView] = useState<string | null>(null);
  const editable = ['draft', 'pending'].includes(listing.status);
  async function update(action: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    try {
      await action();
      const response = await fetch('/api/bql/listings', { cache: 'no-store' });
      if (!response.ok) throw new Error('Tải lại danh sách để xem đúng phiên bản ảnh.');
      const rows: Listing[] = await response.json();
      const next = rows.find((r) => r.id === listing.id);
      if (!next) throw new Error('Tin không còn trong danh sách; đóng chi tiết và làm mới.');
      onChange(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chưa xác định kết quả, hãy làm mới.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className={styles.panel} aria-label="Ảnh sản phẩm riêng tư">
      <h3>Ảnh sản phẩm</h3>
      <p className="field-help">
        Ảnh chỉ qua phiên BQL. Kết quả clear không xác minh hàng thật hoặc độ tin cậy người bán.
      </p>
      <div className={styles.grid}>
        {(listing.images || []).map((image, index) => (
          <article key={image.id} className={styles.card}>
            <button
              type="button"
              className={styles.thumbnail}
              onClick={() => setView(view === image.id ? null : image.id)}
              aria-label={`Xem ảnh sản phẩm ${index + 1}`}
            >
              <Image
                unoptimized
                src={`/api/bql/images/${image.id}`}
                alt={`Ảnh sản phẩm ${index + 1}`}
                width={120}
                height={100}
              />
            </button>
            <strong>{states[image.status]}</strong>
            <small>{image.categories.join(', ') || 'Chưa có nhãn nội dung'}</small>
            <small>
              {image.model} · phiên bản {image.revision.slice(0, 8)}
            </small>
            {editable && (
              <button
                type="button"
                className="row-action"
                disabled={busy}
                onClick={() => void update(() => mutate(`images/${image.id}/recheck`, {}))}
              >
                Kiểm tra ảnh lại
              </button>
            )}
          </article>
        ))}
      </div>
      {view && (
        <div className={styles.viewer}>
          <Image
            unoptimized
            src={`/api/bql/images/${view}`}
            alt="Ảnh riêng tư để BQL kiểm tra"
            width={480}
            height={400}
          />
          <button type="button" className="row-action" onClick={() => setView(null)}>
            Thu gọn ảnh
          </button>
        </div>
      )}
      {editable && (
        <label className={styles.upload}>
          Thêm ảnh JPEG, PNG hoặc WebP · tối đa 4 MiB, 5 ảnh
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={busy || (listing.images?.length || 0) >= 5}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = '';
              if (!file) return;
              if (file.size > 4 * 1024 * 1024) {
                setError('Ảnh tối đa 4 MiB.');
                return;
              }
              void update(async () => {
                const encoded = await new Promise<string>((resolve, reject) => {
                  const reader = new FileReader();
                  reader.onerror = () => reject(new Error('Không đọc được ảnh.'));
                  reader.onload = () => resolve(String(reader.result).split(',')[1]);
                  reader.readAsDataURL(file);
                });
                return mutate(`listings/${listing.id}/images`, { image_base64: encoded });
              });
            }}
          />
        </label>
      )}
      {busy && <p role="status">Đang lưu và kiểm tra ảnh…</p>}
      {error && <Notice message={error} />}
    </section>
  );
}
