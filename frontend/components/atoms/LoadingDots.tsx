import { classNames } from '@/lib/utils';

interface LoadingDotsProps {
  className?: string;
  size?: 'sm' | 'md';
}

export function LoadingDots({ className, size = 'md' }: LoadingDotsProps) {
  const dotSize = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2';

  return (
    <div
      className={classNames('inline-flex items-center gap-1.5', className)}
      role="status"
      aria-label="Loading"
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={classNames(
            dotSize,
            'bg-gold rounded-full animate-pulse'
          )}
          style={{
            animationDelay: `${i * 150}ms`,
            animationDuration: '1.2s',
          }}
        />
      ))}
    </div>
  );
}
