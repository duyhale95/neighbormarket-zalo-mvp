import Link from 'next/link';
export default function NotFound() {
  return (
    <main id="main" className="route-error">
      <span className="section-kicker">404</span>
      <h1>Trang này chưa có ở đây.</h1>
      <Link className="button button-navy" href="/">
        Về NeighborMarket AI
      </Link>
    </main>
  );
}
