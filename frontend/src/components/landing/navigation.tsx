'use client';
import Link from 'next/link';
import { useState } from 'react';
import { ArrowUpRight, Menu, X } from 'lucide-react';
import { VinhomesLogo } from '@/components/brand';
const links = [
  ['Giải pháp', '#giai-phap'],
  ['Quy trình', '#quy-trinh'],
  ['Kiểm duyệt', '#kiem-duyet'],
  ['FAQ', '#faq'],
];
export function Navigation() {
  const [open, setOpen] = useState(false);
  return (
    <header className="landing-header">
      <nav className="landing-nav" aria-label="Điều hướng chính">
        <Link href="/" className="landing-brand" aria-label="NeighborMarket AI — về đầu trang">
          <VinhomesLogo />
          <span className="brand-divider" />
          <span>
            NeighborMarket<span className="ai-word"> AI</span>
          </span>
        </Link>
        <div className="nav-links">
          {links.map(([name, href]) => (
            <a key={href} href={href}>
              {name}
            </a>
          ))}
        </div>
        <Link href="/bql" className="button button-navy nav-cta">
          BQL Dashboard
          <ArrowUpRight size={16} />
        </Link>
        <button
          className="mobile-toggle icon-button"
          aria-label={open ? 'Đóng menu' : 'Mở menu'}
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen(!open)}
        >
          {open ? <X size={21} /> : <Menu size={21} />}
        </button>
      </nav>
      {open && (
        <div
          className="mobile-nav"
          id="mobile-nav"
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false);
          }}
        >
          {links.map(([name, href]) => (
            <a key={href} href={href} onClick={() => setOpen(false)}>
              {name}
              <ArrowUpRight size={16} />
            </a>
          ))}
          <Link href="/bql" onClick={() => setOpen(false)}>
            BQL Dashboard
            <ArrowUpRight size={16} />
          </Link>
        </div>
      )}
    </header>
  );
}
