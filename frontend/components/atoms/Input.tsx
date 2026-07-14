import { forwardRef } from 'react';
import { classNames } from '@/lib/utils';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, label, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-[0.75rem] font-semibold uppercase tracking-[0.08em] text-fern mb-1.5"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={classNames(
            'w-full bg-[#121B16]/60 border border-white/[0.08] rounded-button px-3.5 py-2.5 text-sm text-ivory placeholder:text-muted',
            'transition-all duration-300 ease-brand',
            'focus:outline-none focus:border-gold/40 focus:shadow-[0_0_0_3px_rgba(212,168,83,0.1)]',
            'hover:border-white/[0.12]',
            error && 'border-rose/50 animate-[shake_0.3s_ease-in-out]',
            className
          )}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...props}
        />
        {error && (
          <p
            id={`${inputId}-error`}
            className="mt-1 text-xs text-rose"
            role="alert"
          >
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
