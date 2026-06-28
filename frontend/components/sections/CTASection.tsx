'use client';

import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/atoms/Button';
import { useRouter } from 'next/navigation';

export function CTASection() {
  const router = useRouter();

  return (
    <section className="py-24 px-4 relative overflow-hidden">
      {/* Intensified gradient orbs */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute w-[500px] h-[500px] rounded-full opacity-30 animate-pulse"
          style={{
            background: 'radial-gradient(circle, #D4A853, transparent 70%)',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            filter: 'blur(80px)',
          }}
        />
        <div
          className="absolute w-[400px] h-[400px] rounded-full opacity-20 animate-drift"
          style={{
            background: 'radial-gradient(circle, #7FB069, transparent 70%)',
            top: '20%',
            left: '20%',
            filter: 'blur(100px)',
          }}
        />
        <div
          className="absolute w-[350px] h-[350px] rounded-full opacity-15 animate-drift-slow"
          style={{
            background: 'radial-gradient(circle, #5EEAD4, transparent 70%)',
            bottom: '20%',
            right: '20%',
            filter: 'blur(100px)',
          }}
        />
      </div>

      <div className="max-w-3xl mx-auto text-center relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2 className="text-3xl sm:text-4xl font-bold text-ivory tracking-[-0.02em] mb-4">
            Ready to Build Your AI?
          </h2>
          <p className="text-lg text-fern mb-10 max-w-xl mx-auto">
            Join thousands of creators building custom AI assistants. Start for free, no credit card required.
          </p>

          <motion.div
            animate={{ scale: [1, 1.02, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          >
            <Button
              icon={ArrowRight}
              iconPosition="right"
              onClick={() => router.push('/signup')}
            >
              Get Started Free
            </Button>
          </motion.div>

          <p className="text-xs text-muted mt-6">
            Free tier includes 3 models, 1GB data, and 1000 API calls/month
          </p>
        </motion.div>
      </div>
    </section>
  );
}
