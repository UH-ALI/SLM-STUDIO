import { classNames } from '@/lib/utils';

type SpinnerVariant = 'default' | 'button-overlay' | 'page-overlay';

interface SpinnerProps {
  variant?: SpinnerVariant;
  size?: number;
  className?: string;
  label?: string;
}

export function Spinner({
  variant = 'default',
  size = 24,
  className,
  label = 'Loading...',
}: SpinnerProps) {
  const spinnerContent = (
    <div
      className={classNames(
        'border-2 border-gold/30 border-t-gold rounded-full animate-spin',
        className
      )}
      style={{ width: size, height: size }}
      role="status"
      aria-label={label}
    />
  );

  if (variant === 'page-overlay') {
    return (
      <div className="fixed inset-0 bg-void/80 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="flex flex-col items-center gap-4">
          {spinnerContent}
          <span className="text-sm text-fern">{label}</span>
        </div>
      </div>
    );
  }

  if (variant === 'button-overlay') {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-inherit rounded-inherit">
        <div
          className="border-2 border-current border-t-transparent rounded-full animate-spin"
          style={{ width: size * 0.75, height: size * 0.75 }}
          role="status"
        />
      </div>
    );
  }

  return spinnerContent;
}
