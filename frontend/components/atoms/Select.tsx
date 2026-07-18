import { forwardRef } from 'react';
import { classNames } from '@/lib/utils';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options: SelectOption[];
  error?: string;
  label?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, options, error, label, id, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-[0.75rem] font-semibold uppercase tracking-[0.08em] text-fern mb-1.5"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            className={classNames(
              'w-full bg-[#121B16]/60 border border-white/[0.08] rounded-button px-3.5 py-2.5 text-sm text-ivory appearance-none',
              'transition-all duration-300 ease-brand cursor-pointer',
              'focus:outline-none focus:border-gold/40 focus:shadow-[0_0_0_3px_rgba(212,168,83,0.1)]',
              'hover:border-white/[0.12]',
              error && 'border-rose/50',
              className
            )}
            aria-invalid={!!error}
            aria-describedby={error ? `${selectId}-error` : undefined}
            {...props}
          >
            {options.map((option) => (
              <option
                key={option.value}
                value={option.value}
                className="bg-elevated text-ivory"
              >
                {option.label}
              </option>
            ))}
          </select>
          {/* Custom chevron */}
          <svg
            className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fern pointer-events-none"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        {error && (
          <p
            id={`${selectId}-error`}
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

Select.displayName = 'Select';
