'use client';

import { useState, useEffect } from 'react';
import { Brain } from 'lucide-react';
import { classNames } from '@/lib/utils';

const defaultLoadingMessages = [
  'Initializing model...',
  'Loading dataset...',
  'Preparing training environment...',
  'Configuring hyperparameters...',
  'Starting training process...',
];

interface LoadingBufferProps {
  className?: string;
  messages?: string[];
}

export function LoadingBuffer({ className, messages = defaultLoadingMessages }: LoadingBufferProps) {
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messages.length);
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div
      className={classNames(
        'fixed inset-0 z-50 flex items-center justify-center',
        'bg-void/90 backdrop-blur-xl',
        className
      )}
    >
      <div className="flex flex-col items-center gap-6">
        {/* Pulsing logo */}
        <div className="relative">
          <div className="absolute inset-0 bg-gold/20 rounded-3xl animate-ping" />
          <div
            className={classNames(
              'w-20 h-20 rounded-3xl bg-gradient-to-br from-gold to-sage',
              'flex items-center justify-center relative animate-pulse'
            )}
          >
            <Brain size={40} className="text-void" />
          </div>
        </div>

        {/* Cycling text */}
        <div className="h-6 flex items-center justify-center">
          <p
            key={messageIndex}
            className="text-sm text-fern animate-fade-in text-center"
          >
            {messages[messageIndex]}
          </p>
        </div>

        {/* Progress bar */}
        <div className="w-48 h-1 bg-white/[0.06] rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-gold to-sage rounded-full transition-all duration-500 ease-brand"
            style={{ width: `${((messageIndex + 1) / messages.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
