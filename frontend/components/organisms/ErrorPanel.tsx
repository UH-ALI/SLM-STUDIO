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

function getFriendlyErrorMessage(msg: string): string {
  if (!msg) return 'An unexpected error occurred during training. Please check your configuration and try again.';
  
  const lowerMsg = msg.toLowerCase();
  
  if (lowerMsg.includes('out of memory') || lowerMsg.includes('oom') || lowerMsg.includes('cudaerror') || lowerMsg.includes('runtimeerror') || lowerMsg.includes('out of bounds') || lowerMsg.includes('acceleratorerror') || lowerMsg.includes('accelerate')) {
    return 'The training process exceeded your computer’s available hardware resources. This usually happens when the model or the batches of data are too large for your graphics card (VRAM) to handle at once. We highly recommend clicking "Retry" and accepting the Safe Fallback Defaults to lower the resource footprint.';
  }
  
  if (lowerMsg.includes('unauthorized') || lowerMsg.includes('hf_token') || lowerMsg.includes('401') || lowerMsg.includes('authentication')) {
    return 'We were unable to authenticate with Hugging Face to download the requested model. Please verify that your Hugging Face API token is valid and has "read" permissions in your settings, then try again.';
  }
  
  if (lowerMsg.includes('dataset') || lowerMsg.includes('train.jsonl') || lowerMsg.includes('empty') || lowerMsg.includes('jsondecodeerror') || lowerMsg.includes('formatting')) {
    return 'There was a problem preparing your training data. The system could not properly read the documents or text you provided. Please ensure your uploaded documents contain valid, readable text and are not entirely empty or corrupted.';
  }

  if (lowerMsg.includes('timeout') || lowerMsg.includes('connection') || lowerMsg.includes('network') || lowerMsg.includes('socket')) {
    return 'The connection to the server or model repository timed out. This is typically a temporary network issue. Please check your internet connection and try again.';
  }

  if (lowerMsg.includes('not found') || lowerMsg.includes('404')) {
    return 'The specified Base Model could not be found. It may have been removed, made private, or the name might be misspelled. Please select a different base model from the configuration page.';
  }
  
  return 'An unexpected internal error occurred during the training process. Please check the logs for more details or try running the process again with different settings.';
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
        {getFriendlyErrorMessage(errorMessage)}
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
