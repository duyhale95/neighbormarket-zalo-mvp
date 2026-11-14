import Image from 'next/image';
import { ArrowUpRight, Sun } from 'lucide-react';
export function ProjectMark({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`project-mark ${compact ? 'compact' : ''}`}>
      <span className="project-symbol">
        <Sun size={22} strokeWidth={1.5} />
      </span>
      <span>
        NeighborMarket<span className="ai-word"> AI</span>
      </span>
    </span>
  );
}
export function VinhomesLogo({ className = '' }: { className?: string }) {
  return (
    <Image
      className={`vinhomes-logo ${className}`}
      src="/brand/vinhomes-logo.png"
      alt="Vinhomes — logo do người dùng cung cấp"
      width={1200}
      height={633}
      unoptimized
    />
  );
}
export function ArrowLink({
  href,
  children,
  className = '',
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <a href={href} className={`button ${className}`}>
      {children}
      <ArrowUpRight size={18} />
    </a>
  );
}
