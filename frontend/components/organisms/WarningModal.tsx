'use client';

import { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Button } from '@/components/atoms/Button';

interface WarningModalProps {
  title?: string;
  description?: string;
  onCancel: () => void;
  onContinue: () => void;
}

export function WarningModal({ 
  title = "Advanced Settings",
  description = "The model has been pre-configured with optimal parameters based on your dataset and use case. Altering these settings can create both negative and positive impacts on your model's performance.",
  onCancel, 
  onContinue 
}: WarningModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
  const firstFocusRef = useRef<HTMLButtonElement>(null);

  // Focus trap
  useEffect(() => {
    firstFocusRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-4 pt-12 sm:pt-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="warning-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-void/80 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className={classNames(
          'relative w-full max-w-md glass-card z-10',
          'animate-scale-in'
        )}
      >
        {/* Icon */}
        <div className="w-12 h-12 rounded-xl bg-gold/10 flex items-center justify-center mb-4">
          <AlertTriangle size={24} className="text-gold" />
        </div>

        {/* Title */}
        <h3
          id="warning-title"
          className="text-lg font-semibold text-ivory mb-3"
        >
          {title}
        </h3>

        {/* Description */}
        <p className="text-sm text-fern leading-relaxed mb-6">
          {description}
        </p>

        {/* Actions */}
        <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center gap-3 justify-end">
          <Button
            ref={firstFocusRef}
            variant="secondary"
            onClick={onCancel}
            className="w-full sm:w-auto"
          >
            Cancel
          </Button>
          <Button onClick={onContinue} className="w-full sm:w-auto">
            Continue
          </Button>
        </div>
      </div>
    </div>
  );
}
