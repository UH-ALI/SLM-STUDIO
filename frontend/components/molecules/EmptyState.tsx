import { classNames } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';
import { Button } from '@/components/atoms/Button';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={classNames(
        'flex flex-col items-center justify-center text-center py-16 px-6',
        className
      )}
    >
      {/* Icon */}
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center mb-5">
        <Icon size={32} className="text-gold" />
      </div>

      {/* Title */}
      <h3 className="text-lg font-semibold text-ivory mb-2">{title}</h3>

      {/* Description */}
      <p className="text-sm text-fern max-w-sm mb-6 leading-relaxed">
        {description}
      </p>

      {/* Action */}
      {actionLabel && onAction && (
        <Button onClick={onAction} icon={Icon}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
