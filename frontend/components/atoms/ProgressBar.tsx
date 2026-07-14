import { classNames } from '@/lib/utils';

type ProgressVariant = 'default' | 'training' | 'success' | 'error';

interface ProgressBarProps {
  value: number;
  max?: number;
  variant?: ProgressVariant;
  showValue?: boolean;
  className?: string;
  label?: string;
}

const variantClasses: Record<ProgressVariant, string> = {
  default: 'from-gold to-sage',
  training: 'from-gold to-sage',
  success: 'from-mint to-sage',
  error: 'from-rose to-amber',
};

export function ProgressBar({
  value,
  max = 100,
  variant = 'default',
  showValue = false,
  className,
  label,
}: ProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className={classNames('w-full', className)}>
      {(label || showValue) && (
        <div className="flex items-center justify-between mb-1.5">
          {label && (
            <span className="text-xs text-fern">{label}</span>
          )}
          {showValue && (
            <span className="font-mono text-xs text-gold tabular-nums">
              {percentage.toFixed(0)}%
            </span>
          )}
        </div>
      )}
      <div className="relative w-full h-2 bg-white/[0.06] rounded-full overflow-hidden">
        <div
          className={classNames(
            'absolute top-0 left-0 h-full rounded-full bg-gradient-to-r transition-all duration-500 ease-brand',
            variantClasses[variant]
          )}
          style={{ width: `${percentage}%` }}
        >
          {/* Shimmer overlay */}
          <div className="absolute inset-0 overflow-hidden rounded-full">
            <div className="absolute inset-0 shimmer opacity-30" />
          </div>
        </div>
      </div>
    </div>
  );
}
