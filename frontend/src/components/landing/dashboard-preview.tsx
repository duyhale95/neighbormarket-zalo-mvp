import {
  AlertTriangle,
  ArrowRight,
  Check,
  LayoutDashboard,
  PackageCheck,
  ShieldCheck,
  Sun,
} from 'lucide-react';
import { ArrowLink } from '@/components/brand';
import { Reveal } from './reveal';
export function DashboardPreview() {
  return (
    <section className="preview-section">
      <div className="section-wrap">
        <Reveal>
          <div className="section-header inline-header">
            <div>
              <span className="section-kicker">MỘT GÓC NHÌN RÕ RÀNG HƠN CHO BQL</span>
              <h2>
                Quản lý cộng đồng.
                <br />
                Bắt đầu từ từng tin nhỏ.
              </h2>
            </div>
            <ArrowLink href="/bql" className="button-navy">
              Mở BQL Dashboard
            </ArrowLink>
          </div>
        </Reveal>
        <Reveal className="dashboard-preview">
          <div className="preview-window">
            <span />
            <span />
            <span />
            <p>NeighborMarket AI · Không gian BQL</p>
            <small>DỮ LIỆU MINH HỌA</small>
          </div>
          <div className="preview-app">
            <aside>
              <Sun size={26} />
              <span>
                <LayoutDashboard size={16} />
                Tổng quan
              </span>
              <span className="active">
                <ShieldCheck size={16} />
                Kiểm duyệt tin
              </span>
              <span>
                <PackageCheck size={16} />
                Xuất bản nhóm
              </span>
              <div>
                AI hỗ trợ.
                <br />
                BQL quyết định.
              </div>
            </aside>
            <div className="preview-main">
              <div className="preview-heading">
                <div>
                  <small>KIỂM DUYỆT NỘI DUNG</small>
                  <h3>Những kết nối đáng tin.</h3>
                </div>
                <span>Không gian demo</span>
              </div>
              <div className="preview-metrics">
                <div>
                  <span>Tin đăng minh họa</span>
                  <strong>04</strong>
                </div>
                <div>
                  <span>Chờ kiểm duyệt</span>
                  <strong>02</strong>
                </div>
                <div>
                  <span>Đã phê duyệt</span>
                  <strong>01</strong>
                </div>
                <div>
                  <span>Đã từ chối</span>
                  <strong>01</strong>
                </div>
              </div>
              <div className="preview-table">
                <div className="preview-table-head">
                  <span>Sản phẩm / Mã tin</span>
                  <span>Giá bán</span>
                  <span>Trạng thái</span>
                </div>
                {[
                  {
                    name: 'Bàn học gỗ',
                    id: 'NM-DEMO-001',
                    price: '450.000đ',
                    status: 'Chờ duyệt',
                    warn: false,
                  },
                  {
                    name: 'Ghế công thái học',
                    id: 'NM-DEMO-002',
                    price: '800.000đ',
                    status: 'Cần kiểm tra',
                    warn: true,
                  },
                  {
                    name: 'Kệ sách nhỏ',
                    id: 'NM-DEMO-003',
                    price: '250.000đ',
                    status: 'Đã duyệt',
                    warn: false,
                  },
                ].map((row) => (
                  <div className="preview-table-row" key={row.id}>
                    <span>
                      <strong>{row.name}</strong>
                      <small>{row.id}</small>
                    </span>
                    <span>{row.price}</span>
                    <span className={row.warn ? 'preview-warning' : 'preview-status'}>
                      {row.warn ? <AlertTriangle size={11} /> : <Check size={11} />} {row.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Reveal>
        <div className="preview-below">
          <span>
            <ShieldCheck size={16} /> Duyệt nội dung · Theo dõi delivery · Đối soát kết quả
          </span>
          <a href="/bql">
            Đăng nhập để xem dữ liệu backend thật
            <ArrowRight size={15} />
          </a>
        </div>
      </div>
    </section>
  );
}
