'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { useUIStore } from '@/stores/uiStore';

const iconMap = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const colorMap = {
  success: 'text-mint bg-mint/10 border-mint/20',
  error: 'text-rose bg-rose/10 border-rose/20',
  warning: 'text-amber bg-amber/10 border-amber/20',
  info: 'text-gold bg-gold/10 border-gold/20',
};

export function ToastContainer() {
  const { toasts, removeToast } = useUIStore();

  return (
    <div
      className="fixed top-4 left-4 right-4 sm:left-auto sm:right-4 z-[100] flex flex-col gap-2 w-auto sm:w-80"
      aria-live="polite"
      aria-atomic="true"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => {
          const Icon = iconMap[toast.type];
          const colors = colorMap[toast.type];

          return (
            <motion.div
              key={toast.id}
              initial={{ x: 100, opacity: 0, scale: 0.9 }}
              animate={{ x: 0, opacity: 1, scale: 1 }}
              exit={{ x: 100, opacity: 0, scale: 0.9 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              layout
              onHoverStart={() => {
                // Pause auto-dismiss on hover would go here
              }}
              className={classNames(
                'flex items-start gap-3 p-3 rounded-xl border backdrop-blur-sm',
                'bg-[#121B16]/95 shadow-glass',
                colors,
                'w-full'
              )}
            >
              <Icon size={18} className="flex-shrink-0 mt-0.5" />
              <p className="flex-1 text-sm text-ivory/90">{toast.message}</p>
              <button
                onClick={() => removeToast(toast.id)}
                className="flex-shrink-0 p-0.5 rounded text-fern hover:text-ivory transition-colors"
                aria-label="Dismiss notification"
              >
                <X size={14} />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
