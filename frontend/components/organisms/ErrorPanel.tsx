'use client';

import { AlertCircle, RotateCcw, FileText } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Button } from '@/components/atoms/Button';

interface ErrorPanelProps {
  errorMessage: string;
  onRetry?: () => void;
  onViewDetails?: () => void;
  className?: string;
}

export function ErrorPanel({ errorMessage, onRetry, onViewDetails, className }: ErrorPanelProps) {
  return (
    <div
      className={classNames(
        'glass-card border-rose/30',
        className
      )}
    >
      {/* Icon */}
      <div className="w-12 h-12 rounded-xl bg-rose/10 flex items-center justify-center mb-4">
        <AlertCircle size={24} className="text-rose" />
      </div>

      {/* Title */}
      <h3 className="text-lg font-semibold text-rose mb-2">Training Failed</h3>

      {/* Error message */}
      <p className="text-sm text-ivory/80 mb-6 leading-relaxed">
        {errorMessage || 'An unexpected error occurred during training. Please check your configuration and try again.'}
      </p>

      {/* Actions */}
      <div className="flex items-center gap-3">
        {onRetry && (
          <Button
            variant="secondary"
            icon={RotateCcw}
            onClick={onRetry}
          >
            Retry
          </Button>
        )}
        {onViewDetails && (
          <Button
            variant="ghost"
            icon={FileText}
            onClick={onViewDetails}
          >
            View Details
          </Button>
        )}
      </div>
    </div>
  );
}
