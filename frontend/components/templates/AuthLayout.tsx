'use client';

import { motion } from 'framer-motion';
import { Brain } from 'lucide-react';
import { classNames } from '@/lib/utils';

interface AuthLayoutProps {
  children: React.ReactNode;
  variant: 'login' | 'signup';
}

function NeuralBackground() {
  // Animated mesh gradient with floating nodes for signup
  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Base gradient */}
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse at 30% 20%, rgba(212,168,83,0.15) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(127,176,105,0.15) 0%, transparent 50%), #0A0F0C',
        }}
      />
      {/* Floating nodes */}
      {Array.from({ length: 15 }, (_, i) => (
        <motion.div
          key={i}
          className="absolute w-2 h-2 rounded-full bg-gold/30"
          style={{
            left: `${10 + Math.random() * 80}%`,
            top: `${10 + Math.random() * 80}%`,
          }}
          animate={{
            y: [0, -20, 0],
            opacity: [0.3, 0.8, 0.3],
          }}
          transition={{
            duration: 3 + Math.random() * 4,
            repeat: Infinity,
            delay: Math.random() * 3,
            ease: 'easeInOut',
          }}
        />
      ))}
      {/* Connection lines (decorative) */}
      <svg className="absolute inset-0 w-full h-full opacity-10">
        <defs>
          <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#D4A853" />
            <stop offset="100%" stopColor="#7FB069" />
          </linearGradient>
        </defs>
        {Array.from({ length: 8 }, (_, i) => (
          <motion.line
            key={i}
            x1={`${10 + Math.random() * 40}%`}
            y1={`${10 + Math.random() * 40}%`}
            x2={`${40 + Math.random() * 50}%`}
            y2={`${30 + Math.random() * 60}%`}
            stroke="url(#lineGrad)"
            strokeWidth="1"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 0.3 }}
            transition={{ duration: 2, delay: i * 0.3, repeat: Infinity, repeatType: 'reverse' }}
          />
        ))}
      </svg>
    </div>
  );
}

function DigitalBrainBackground() {
  // Digital brain pattern for login
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse at 50% 50%, rgba(94,234,212,0.1) 0%, transparent 60%), radial-gradient(ellipse at 80% 30%, rgba(212,168,83,0.1) 0%, transparent 40%), #0A0F0C',
        }}
      />
      {/* Grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(212,168,83,0.5) 1px, transparent 1px),
            linear-gradient(90deg, rgba(212,168,83,0.5) 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px',
        }}
      />
      {/* Orbiting circles */}
      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
        animate={{ rotate: 360 }}
        transition={{ duration: 60, repeat: Infinity, ease: 'linear' }}
      >
        <div className="w-[500px] h-[500px] rounded-full border border-gold/10" />
      </motion.div>
      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
        animate={{ rotate: -360 }}
        transition={{ duration: 45, repeat: Infinity, ease: 'linear' }}
      >
        <div className="w-[350px] h-[350px] rounded-full border border-sage/10" />
      </motion.div>
    </div>
  );
}

export function AuthLayout({ children, variant }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-void relative flex items-start sm:items-center justify-center px-4 py-6 sm:p-4">
      {/* Background */}
      {variant === 'signup' ? <NeuralBackground /> : <DigitalBrainBackground />}

      {/* Card container */}
      <motion.div
        initial={{ y: 30, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 w-full max-w-md"
      >
        {/* Card with organic curved cuts */}
        <div
          className={classNames(
            'relative bg-cream rounded-[24px] p-5 sm:p-8 shadow-2xl overflow-hidden',
            'before:absolute before:inset-y-0 before:left-0 before:w-4 before:bg-gradient-to-b before:from-gold/30 before:via-sage/20 before:to-gold/30',
            'after:absolute after:inset-y-0 after:right-0 after:w-4 after:bg-gradient-to-b after:from-sage/30 after:via-gold/20 after:to-sage/30'
          )}
        >
          {/* Logo */}
          <div className="flex items-center justify-center mb-8">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-gold to-sage flex items-center justify-center">
              <Brain size={24} className="text-void" />
            </div>
          </div>

          {children}
        </div>
      </motion.div>
    </div>
  );
}
