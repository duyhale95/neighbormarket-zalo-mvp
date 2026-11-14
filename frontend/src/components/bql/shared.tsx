import { AlertCircle, CircleCheck, Inbox } from 'lucide-react';
export const labels: Record<string, string> = {
  draft: 'Bản nháp',
  pending: 'Chờ duyệt',
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
  sold: 'Đã bán',
  queued: 'Trong hàng chờ',
  claimed: 'Đang xử lý',
  sent: 'Đã ghi nhận gửi',
  failed: 'Gửi thất bại',
  unknown: 'Cần đối soát',
  cancelled: 'Đã hủy',
};
export const flagLabels: Record<string, string> = {
  sensitive_information: 'Thông tin nhạy cảm',
  profanity: 'Ngôn từ cần kiểm tra',
  spam: 'Dấu hiệu spam',
  suspicious: 'Nội dung đáng ngờ',
  ai_suspicious: 'AI đề nghị kiểm tra',
  prohibited: 'Từ khóa mặt hàng bị cấm',
  external_link: 'Liên kết ngoài',
  abnormal_price: 'Giá cần kiểm tra',
  unknown: 'Cờ chưa xác định',
};
export const sourceLabels: Record<string, string> = {
  legacy: 'Bridge / lệnh hiện có',
  deplao: 'Deplao · Zalo cá nhân',
  mock: 'Giả lập · không phải Zalo thật',
};
export const riskLabels: Record<string, string> = {
  low: 'Chưa thấy dấu hiệu theo luật demo',
  attention: 'Có điểm cần BQL xác minh',
  high: 'Nội dung bị chặn theo chính sách',
};
export const evidenceLabels: Record<string, string> = {
  mock: 'Giả lập · không gửi Zalo thật',
  deplao: 'Deplao · cần đối chiếu nhóm',
  unverified: 'Transport chưa xác minh',
  manual: 'BQL đã đối soát thủ công',
};
export function Status({ value }: { value: string }) {
  return (
    <span className={`status status-${value}`}>
      <i />
      {labels[value] || value}
    </span>
  );
}
export const money = (n: number) =>
  new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
    maximumFractionDigits: 0,
  }).format(n);
export function date(value: string) {
  const parsed = new Date(value.replace(' ', 'T') + 'Z');
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString('vi-VN', {
        timeZone: 'Asia/Ho_Chi_Minh',
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      });
}
export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty-state">
      <Inbox size={32} />
      <h3>Chưa có dữ liệu ở đây</h3>
      <p>{children}</p>
    </div>
  );
}
export function Notice({ message, success = false }: { message: string; success?: boolean }) {
  return (
    <div
      className={`notice ${success ? 'notice-success' : ''}`}
      role={success ? 'status' : 'alert'}
    >
      {success ? <CircleCheck size={18} /> : <AlertCircle size={18} />}
      <span>{message}</span>
    </div>
  );
}
