import { LandingLayout } from '@/components/templates/LandingLayout';
import { HeroSection } from '@/components/sections/HeroSection';
import { HowItWorks } from '@/components/sections/HowItWorks';
import { WhyChoose } from '@/components/sections/WhyChoose';
import { CTASection } from '@/components/sections/CTASection';

export default function LandingPage() {
  return (
    <LandingLayout>
      <HeroSection />
      <HowItWorks />
      <WhyChoose />
      <CTASection />
    </LandingLayout>
  );
}
