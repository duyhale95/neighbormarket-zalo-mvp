import { Navigation } from '@/components/landing/navigation';
import { Hero } from '@/components/landing/hero';
import { Scenarios } from '@/components/landing/scenarios';
import { Phones } from '@/components/landing/phones';
import { Features } from '@/components/landing/features';
import { DashboardPreview } from '@/components/landing/dashboard-preview';
import { Community, FinalCTA, Footer } from '@/components/landing/community';
import { FAQ } from '@/components/landing/faq';
export default function Home() {
  return (
    <div className="landing">
      <Navigation />
      <main id="main">
        <Hero />
        <Scenarios />
        <Phones />
        <Features />
        <DashboardPreview />
        <Community />
        <FinalCTA />
        <FAQ />
      </main>
      <Footer />
    </div>
  );
}
