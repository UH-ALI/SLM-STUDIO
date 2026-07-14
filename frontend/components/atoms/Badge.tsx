import { classNames } from '@/lib/utils';

type BadgeVariant = 'deployed' | 'training' | 'ready' | 'failed';

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  pulse?: boolean;
}

const variantClasses: Record<BadgeVariant, string> = {
  deployed: 'bg-mint/10 border-mint/20 text-mint',
  training: 'bg-gold/10 border-gold/20 text-gold',
  ready: 'bg-sage/10 border-sage/20 text-sage',
  failed: 'bg-rose/10 border-rose/20 text-rose',
};

export function Badge({ variant, children, className, pulse = false }: BadgeProps) {
  return (
    <span
      className={classNames(
        'inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium border rounded-full',
        variantClasses[variant],
        className
      )}
    >
      {variant === 'training' && (
        <span
          className={classNames(
            'w-1.5 h-1.5 rounded-full bg-current',
            pulse && 'animate-pulse'
          )}
        />
      )}
      {children}
    </span>
  );
}
