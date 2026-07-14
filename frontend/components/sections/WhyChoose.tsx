'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import {
  Shield,
  Zap,
  Lock,
  Sparkles,
  Server,
  Gauge,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface Feature {
  icon: LucideIcon;
  title: string;
  description: string;
}

const features: Feature[] = [
  {
    icon: Shield,
    title: 'Private & Secure',
    description: 'Your data never leaves your control. Full encryption at rest and in transit.',
  },
  {
    icon: Zap,
    title: 'Lightning Fast',
    description: 'Train models in under 5 minutes with our optimized infrastructure.',
  },
  {
    icon: Lock,
    title: 'Data Ownership',
    description: 'You own your data and your models. Export anytime, no vendor lock-in.',
  },
  {
    icon: Sparkles,
    title: 'No Code Required',
    description: 'Built for everyone. No ML expertise or engineering team needed.',
  },
  {
    icon: Server,
    title: 'Scalable Infrastructure',
    description: 'From prototype to production, scale effortlessly with our cloud.',
  },
  {
    icon: Gauge,
    title: 'Real-time Monitoring',
    description: 'Watch your model train live with detailed metrics and logs.',
  },
];

function FeatureCard({ feature, index }: { feature: Feature; index: number }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });
  const Icon = feature.icon;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
      className="glass-card group hover:scale-[1.02] transition-transform duration-300"
    >
      <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
        <Icon size={22} className="text-gold" />
      </div>
      <h3 className="text-sm font-bold text-ivory mb-2">{feature.title}</h3>
      <p className="text-xs text-fern leading-relaxed">{feature.description}</p>
    </motion.div>
  );
}

export function WhyChoose() {
  return (
    <section className="py-24 px-4 relative">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="text-[0.75rem] font-semibold uppercase tracking-[0.08em] text-gold mb-3">
            Why Choose Us
          </h2>
          <h3 className="text-3xl sm:text-4xl font-bold text-ivory tracking-[-0.02em]">
            Built for the Future
          </h3>
        </motion.div>

        {/* Features grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((feature, index) => (
            <FeatureCard key={feature.title} feature={feature} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
