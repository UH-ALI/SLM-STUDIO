import { forwardRef } from 'react';
import { classNames } from '@/lib/utils';

interface SliderProps {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  label?: string;
  showValue?: boolean;
  formatValue?: (value: number) => string;
  disabled?: boolean;
}

export const Slider = forwardRef<HTMLInputElement, SliderProps>(
  (
    {
      value,
      onChange,
      min,
      max,
      step = 1,
      label,
      showValue = true,
      formatValue,
      disabled = false,
    },
    ref
  ) => {
    const percentage = ((value - min) / (max - min)) * 100;

    const defaultFormat = (v: number): string => {
      if (v < 0.001) return v.toExponential(0);
      if (v < 0.01) return v.toFixed(4);
      if (v < 1) return v.toFixed(2);
      return v.toFixed(0);
    };

    const displayValue = (formatValue || defaultFormat)(value);

    return (
      <div className="w-full">
        <div className="flex items-center justify-between mb-2">
          {label && (
            <label className="text-[0.75rem] font-semibold uppercase tracking-[0.08em] text-fern">
              {label}
            </label>
          )}
          {showValue && (
            <span className="font-mono text-sm font-semibold text-gold tabular-nums">
              {displayValue}
            </span>
          )}
        </div>
        <div className="relative w-full h-2 bg-white/[0.06] rounded-full">
          {/* Fill */}
          <div
            className="absolute top-0 left-0 h-full rounded-full bg-gradient-to-r from-gold to-sage"
            style={{ width: `${percentage}%` }}
          />
          {/* Native range input */}
          <input
            ref={ref}
            type="range"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(parseFloat(e.target.value))}
            disabled={disabled}
            className={classNames(
              'absolute top-1/2 -translate-y-1/2 left-0 w-full h-4 -mt-2 opacity-0 cursor-pointer',
              disabled && 'cursor-not-allowed'
            )}
            aria-label={label}
            aria-valuemin={min}
            aria-valuemax={max}
            aria-valuenow={value}
          />
          {/* Custom thumb */}
          <div
            className={classNames(
              'absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-[0_0_10px_rgba(212,168,83,0.5)] cursor-pointer',
              'transition-transform duration-150 hover:scale-125',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
            style={{ left: `calc(${percentage}% - 8px)` }}
          />
        </div>
      </div>
    );
  }
);

Slider.displayName = 'Slider';
