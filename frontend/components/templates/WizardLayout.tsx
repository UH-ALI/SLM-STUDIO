'use client';

import { motion } from 'framer-motion';
import { Stepper } from '@/components/molecules/Stepper';

interface WizardLayoutProps {
  children: React.ReactNode;
  currentStep: number;
}

const steps = [
  { label: 'Setup', description: 'Configure your project' },
  { label: 'Upload', description: 'Add your data' },
  { label: 'Configure', description: 'Fine-tune settings' },
];

export function WizardLayout({ children, currentStep }: WizardLayoutProps) {
  return (
    <div className="min-h-screen bg-void py-8 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Stepper */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8"
        >
          <Stepper steps={steps} currentStep={currentStep} />
        </motion.div>

        {/* Content area */}
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="glass-card"
        >
          {children}
        </motion.div>
      </div>
    </div>
  );
}
