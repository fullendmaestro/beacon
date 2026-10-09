import { SiteHeader } from "@/components/landing/site-header";
import { SiteFooter } from "@/components/landing/site-footer";
import { HeroSection } from "@/components/landing/hero-section";
import { FeaturesSection } from "@/components/landing/features-section";

export default function BeaconLandingPage() {
  return (
    <div
      data-slot="layout"
      className="group/layout relative z-10 flex min-h-svh flex-col bg-background has-data-[slot=designer]:h-svh has-data-[slot=designer]:overflow-hidden"
    >
      <SiteHeader />
      <main className="flex min-h-0 flex-1 flex-col">
        <HeroSection />
        <FeaturesSection />
      </main>
      <SiteFooter />
    </div>
  );
}
