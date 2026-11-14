import {
  ArrowLeft,
  BatteryFull,
  Check,
  CheckCheck,
  ChevronRight,
  Ellipsis,
  LockKeyhole,
  Plus,
  Send,
  ShieldCheck,
  Signal,
  Sun,
  Wifi,
} from 'lucide-react';
function PhoneFrame({
  children,
  title,
  subtitle,
  kind,
}: {
  children: React.ReactNode;
  title: string;
  subtitle: string;
  kind: string;
}) {
  return (
    <article className={`phone phone-${kind}`} aria-label={`${title}, giao diện minh họa`}>
      <div className="phone-status">
        <span>9:41</span>
        <span className="phone-island" />
        <span>
          <Signal size={12} />
          <Wifi size={12} />
          <BatteryFull size={16} />
        </span>
      </div>
      <div className="phone-nav">
        <ArrowLeft size={18} />
        <span className="chat-avatar">
          <Sun size={19} />
        </span>
        <div>
          <strong>{title}</strong>
          <small>{subtitle}</small>
        </div>
        <Ellipsis size={20} />
      </div>
      {children}
      <div className="phone-home" />
    </article>
  );
}
function ListingMini() {
  return (
    <div className="listing-mini">
      <div className="mini-product-art" aria-hidden="true">
        <span className="desk-top" />
        <span className="desk-leg left" />
        <span className="desk-leg right" />
        <span className="desk-book" />
      </div>
      <span className="mini-product-label">BẢN NHÁP · NM-DEMO-001</span>
      <h3>Bàn học gỗ</h3>
      <strong>450.000đ</strong>
      <p>Đã sử dụng 1 năm · Còn tốt</p>
    </div>
  );
}
export function Phones() {
  return (
    <section className="phones-section" id="quy-trinh">
      <div className="section-wrap">
        <div className="section-header centered">
          <span className="section-kicker">TỪ TIN NHẮN ĐẾN NIỀM TIN</span>
          <h2>
            Quen thuộc như một tin nhắn.
            <br />
            An tâm nhờ một quy trình.
          </h2>
          <p>Trợ lý hỗ trợ từng bước. Ban Quản lý luôn giữ quyền quyết định.</p>
          <span className="illustration-label">
            Giao diện minh họa · Dữ liệu demo · Không phải ứng dụng Zalo chính thức
          </span>
        </div>
        <div className="phones-stage">
          <div className="phone-halo" aria-hidden="true" />
          <div className="phone-track">
            <PhoneFrame title="Meo Meo" subtitle="Trợ lý chợ cư dân · Demo" kind="seller">
              <div className="chat-body">
                <div className="chat-date">Hôm nay, 09:41</div>
                <div className="chat-bubble outgoing">
                  Mình muốn bán bàn học gỗ, giá 450 nghìn. Đã sử dụng 1 năm, còn tốt.
                  <small>
                    09:41 <CheckCheck size={11} />
                  </small>
                </div>
                <div className="chat-bubble incoming">
                  Mình đã tạo bản nháp. Bạn kiểm tra và xác nhận để gửi BQL duyệt nhé.
                  <ListingMini />
                </div>
                <div className="chat-bubble outgoing tiny">
                  xacnhan NM-DEMO-001
                  <CheckCheck size={11} />
                </div>
              </div>
              <div className="chat-input">
                <Plus size={17} />
                <span>Nhắn tin cho trợ lý…</span>
                <Send size={16} />
              </div>
            </PhoneFrame>
            <PhoneFrame
              title="Ban Quản lý"
              subtitle="Kiểm duyệt trước khi công khai"
              kind="moderation"
            >
              <div className="moderation-phone-body">
                <div className="phone-step">
                  <span>02</span> KIỂM DUYỆT CÓ CON NGƯỜI
                </div>
                <div className="phone-review-card">
                  <span className="phone-pending">
                    <i /> Chờ Ban Quản lý duyệt
                  </span>
                  <ListingMini />
                  <div className="phone-review-detail">
                    <span>Nội dung nhạy cảm</span>
                    <strong>Chưa phát hiện</strong>
                  </div>
                  <div className="phone-review-detail">
                    <span>Quyết định cuối cùng</span>
                    <strong>Ban Quản lý</strong>
                  </div>
                  <div className="phone-fake-action">
                    <ShieldCheck size={15} /> BQL kiểm tra & quyết định
                  </div>
                </div>
                <div className="phone-rule">
                  <LockKeyhole size={19} />
                  <p>Tin chưa duyệt sẽ không được đưa vào hàng chờ đăng nhóm.</p>
                </div>
                <div className="phone-flow">
                  <span>Nháp</span>
                  <ChevronRight size={12} />
                  <strong>BQL duyệt</strong>
                  <ChevronRight size={12} />
                  <span>Xuất bản</span>
                </div>
              </div>
            </PhoneFrame>
            <PhoneFrame
              title="Chợ cư dân · Legit"
              subtitle="Chỉ đăng tin đã được duyệt"
              kind="group"
            >
              <div className="chat-body">
                <div className="chat-date">Luồng nhóm · Minh họa</div>
                <div className="group-sender">
                  <span className="chat-avatar">
                    <Sun size={17} />
                  </span>
                  <span>
                    Meo Meo <small>Trợ lý cộng đồng</small>
                  </span>
                </div>
                <div className="group-listing">
                  <span className="approved-mini">
                    <ShieldCheck size={13} /> TIN ĐÃ DUYỆT
                  </span>
                  <div className="mini-product-art" aria-hidden="true">
                    <span className="desk-top" />
                    <span className="desk-leg left" />
                    <span className="desk-leg right" />
                    <span className="desk-book" />
                  </div>
                  <h3>Bàn học gỗ</h3>
                  <strong>450.000đ</strong>
                  <p>Tình trạng: Đã sử dụng 1 năm</p>
                  <div className="group-listing-code">NM-DEMO-001</div>
                  <p>Nhắn riêng cho Meo Meo để tìm hiểu sản phẩm.</p>
                  <span className="group-demo-note">
                    <Check size={11} /> Minh họa · Chưa xác minh gửi thật
                  </span>
                </div>
              </div>
              <div className="group-readonly">
                <LockKeyhole size={13} /> Nhóm có kiểm soát quyền đăng
              </div>
            </PhoneFrame>
          </div>
        </div>
        <div className="workflow-caption">
          <span>
            <i /> GỬI RIÊNG
          </span>
          <span className="caption-line" />
          <span>
            <i /> BQL KIỂM DUYỆT
          </span>
          <span className="caption-line" />
          <span>
            <i /> HÀNG CHỜ XUẤT BẢN
          </span>
        </div>
      </div>
    </section>
  );
}
