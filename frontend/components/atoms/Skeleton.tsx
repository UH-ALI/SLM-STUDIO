import { classNames } from '@/lib/utils';

type SkeletonVariant = 'text' | 'circle' | 'card' | 'metric';

interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  className?: string;
  lines?: number;
}

export function Skeleton({
  variant = 'text',
  width,
  height,
  className,
  lines = 1,
}: SkeletonProps) {
  const baseClasses = 'shimmer rounded-lg';

  const variantClasses: Record<SkeletonVariant, string> = {
    text: 'h-4 w-full rounded',
    circle: 'rounded-full',
    card: 'h-32 w-full rounded-card',
    metric: 'h-8 w-20 rounded',
  };

  if (variant === 'text' && lines > 1) {
    return (
      <div className={classNames('space-y-2', className)}>
        {Array.from({ length: lines }, (_, i) => (
          <div
            key={i}
            className={classNames(baseClasses, variantClasses.text)}
            style={{
              width: i === lines - 1 ? '75%' : width,
              height,
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={classNames(baseClasses, variantClasses[variant], className)}
      style={{
        width: variant === 'circle' ? (width || height || 40) : width,
        height: variant === 'circle' ? (height || width || 40) : height,
      }}
      aria-hidden="true"
    />
  );
}
