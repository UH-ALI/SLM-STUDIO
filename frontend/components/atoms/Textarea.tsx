import { forwardRef } from 'react';
import { classNames } from '@/lib/utils';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
  label?: string;
  maxLength?: number;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, label, id, maxLength, value, ...props }, ref) => {
    const textareaId = id || label?.toLowerCase().replace(/\s+/g, '-');
    const charCount = typeof value === 'string' ? value.length : 0;

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={textareaId}
            className="block text-[0.75rem] font-semibold uppercase tracking-[0.08em] text-fern mb-1.5"
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          value={value}
          maxLength={maxLength}
          className={classNames(
            'w-full bg-[#121B16]/60 border border-white/[0.08] rounded-button px-3.5 py-2.5 text-sm text-ivory placeholder:text-muted resize-none',
            'transition-all duration-300 ease-brand',
            'focus:outline-none focus:border-gold/40 focus:shadow-[0_0_0_3px_rgba(212,168,83,0.1)]',
            'hover:border-white/[0.12]',
            error && 'border-rose/50',
            className
          )}
          aria-invalid={!!error}
          aria-describedby={error ? `${textareaId}-error` : undefined}
          rows={4}
          {...props}
        />
        <div className="flex justify-between mt-1">
          {error && (
            <p
              id={`${textareaId}-error`}
              className="text-xs text-rose"
              role="alert"
            >
              {error}
            </p>
          )}
          {maxLength && (
            <span
              className={classNames(
                'text-xs ml-auto tabular-nums',
                charCount > maxLength ? 'text-rose' : 'text-muted'
              )}
            >
              {charCount}/{maxLength}
            </span>
          )}
        </div>
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';
