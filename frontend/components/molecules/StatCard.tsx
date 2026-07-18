import { classNames } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  icon: LucideIcon;
  value: string | number;
  label: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  className?: string;
}

export function StatCard({ icon: Icon, value, label, trend, className }: StatCardProps) {
  return (
    <div
      className={classNames(
        'glass-card p-4 flex items-center gap-4',
        className
      )}
    >
      {/* Icon container */}
      <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center flex-shrink-0">
        <Icon size={22} className="text-gold" strokeWidth={1.5} />
      </div>

      {/* Content */}
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-lg font-semibold text-gold truncate">
            {value}
          </span>
          {trend && (
            <span
              className={classNames(
                'text-xs font-medium tabular-nums',
                trend.isPositive ? 'text-mint' : 'text-rose'
              )}
            >
              {trend.isPositive ? '+' : '-'}{trend.value}%
            </span>
          )}
        </div>
        <p className="text-xs text-fern uppercase tracking-[0.06em]">{label}</p>
      </div>
    </div>
  );
}
