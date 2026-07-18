'use client';

import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Upload, Brain, Rocket } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface Step {
  icon: LucideIcon;
  title: string;
  description: string;
}

const steps: Step[] = [
  {
    icon: Upload,
    title: 'Upload',
    description: 'Upload your documents, PDFs, or text files. Our system processes and prepares your data for training.',
  },
  {
    icon: Brain,
    title: 'Train',
    description: 'Choose your model and hyperparameters. Watch your AI learn in real-time with live metrics and logs.',
  },
  {
    icon: Rocket,
    title: 'Deploy',
    description: 'Deploy your trained model instantly. Chat with it, integrate via API, or share with your team.',
  },
];

function StepCard({ step, index }: { step: Step; index: number }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });
  const Icon = step.icon;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay: index * 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="glass-card text-center group relative"
    >
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center mx-auto mb-5 group-hover:scale-110 transition-transform duration-300">
        <Icon size={28} className="text-gold" />
      </div>
      <h3 className="text-lg font-bold text-ivory mb-3">{step.title}</h3>
      <p className="text-sm text-fern leading-relaxed">{step.description}</p>

      {/* Step number */}
      <div className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-gold/20 border border-gold/30 flex items-center justify-center">
        <span className="text-xs font-bold text-gold">{index + 1}</span>
      </div>
    </motion.div>
  );
}

export function HowItWorks() {
  const sectionRef = useRef(null);

  return (
    <section ref={sectionRef} className="py-20 sm:py-24 px-4 relative">
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
            How It Works
          </h2>
          <h3 className="text-3xl sm:text-4xl font-bold text-ivory tracking-[-0.02em]">
            Three Steps to Your AI
          </h3>
        </motion.div>

        {/* Steps grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {steps.map((step, index) => (
            <StepCard key={step.title} step={step} index={index} />
          ))}
        </div>

        {/* Connector lines (desktop) */}
        <div className="hidden md:block absolute top-1/2 left-1/2 -translate-x-1/2 w-2/3 pointer-events-none">
          <div className="flex justify-between px-20">
            <div className="w-16 h-px bg-gradient-to-r from-transparent to-gold/30" />
            <div className="w-16 h-px bg-gradient-to-r from-gold/30 to-transparent" />
          </div>
        </div>
      </div>
    </section>
  );
}
