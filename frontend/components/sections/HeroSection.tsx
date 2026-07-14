'use client';

import { motion } from 'framer-motion';
import { ArrowRight, Play } from 'lucide-react';
import { Button } from '@/components/atoms/Button';
import { HeroBackground } from '@/components/three/HeroBackground';
import { useRouter } from 'next/navigation';

export function HeroSection() {
  const router = useRouter();

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* 3D Background */}
      <HeroBackground />

      {/* CSS gradient orbs as backup/enhancement */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute w-[600px] h-[600px] rounded-full opacity-20 animate-drift"
          style={{
            background: 'radial-gradient(circle, #D4A853, transparent 70%)',
            top: '5%',
            left: '10%',
            filter: 'blur(80px)',
          }}
        />
        <div
          className="absolute w-[500px] h-[500px] rounded-full opacity-15 animate-drift-slow"
          style={{
            background: 'radial-gradient(circle, #7FB069, transparent 70%)',
            bottom: '10%',
            right: '5%',
            filter: 'blur(80px)',
          }}
        />
        <div
          className="absolute w-[400px] h-[400px] rounded-full opacity-10 animate-drift-fast"
          style={{
            background: 'radial-gradient(circle, #5EEAD4, transparent 70%)',
            top: '40%',
            right: '30%',
            filter: 'blur(80px)',
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 max-w-5xl mx-auto px-4 text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-gold/10 border border-gold/20 mb-8"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse" />
            <span className="text-xs font-medium text-gold">No code required</span>
          </motion.div>

          {/* H1 */}
          <h1
            className="font-extrabold tracking-[-0.03em] text-ivory leading-[1.1] mb-6"
            style={{ fontSize: 'clamp(3rem, 6vw, 5.5rem)' }}
          >
            Train Your Own AI.
            <br />
            <span className="bg-gradient-to-r from-gold via-sage to-mint bg-clip-text text-transparent">
              No Code. No Engineers.
            </span>
          </h1>

          {/* H2 */}
          <p className="text-lg sm:text-xl text-fern max-w-2xl mx-auto mb-10 leading-relaxed">
            Your Data. Your Model. Your AI Assistant — Built in Minutes.
          </p>

          {/* CTAs */}
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <Button
              icon={ArrowRight}
              iconPosition="right"
              onClick={() => router.push('/signup')}
            >
              Get Started
            </Button>
            <Button
              variant="secondary"
              icon={Play}
              iconPosition="left"
              onClick={() => router.push('/dashboard')}
            >
              View Demo
            </Button>
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.8 }}
          className="grid grid-cols-3 gap-8 max-w-lg mx-auto mt-20"
        >
          {[
            { value: '10K+', label: 'Models Trained' },
            { value: '<5min', label: 'Setup Time' },
            { value: '99.9%', label: 'Uptime' },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <p className="font-mono text-2xl font-bold text-gold">{stat.value}</p>
              <p className="text-xs text-fern mt-1">{stat.label}</p>
            </div>
          ))}
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
      >
        <div className="w-6 h-10 rounded-full border-2 border-white/20 flex items-start justify-center p-1.5">
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="w-1 h-2 rounded-full bg-gold"
          />
        </div>
      </motion.div>
    </section>
  );
}
