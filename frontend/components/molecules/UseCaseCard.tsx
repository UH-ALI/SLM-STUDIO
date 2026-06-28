import { classNames } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface UseCaseCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  selected?: boolean;
  onClick: () => void;
}

export function UseCaseCard({
  icon: Icon,
  title,
  description,
  selected = false,
  onClick,
}: UseCaseCardProps) {
  return (
    <button
      onClick={onClick}
      className={classNames(
        'relative w-full text-left p-4 rounded-card border transition-all duration-300 ease-brand',
        'bg-[#121B16]/40 backdrop-blur-sm',
        'focus-visible:outline-2 focus-visible:outline-gold focus-visible:outline-offset-2',
        selected
          ? 'border-gold/50 shadow-[0_0_20px_rgba(212,168,83,0.1)] scale-[1.02]'
          : 'border-white/[0.06] hover:border-gold/20 hover:scale-[1.01] hover:bg-white/[0.02]'
      )}
      role="radio"
      aria-checked={selected}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={classNames(
            'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors',
            selected
              ? 'bg-gradient-to-br from-gold/30 to-sage/30'
              : 'bg-white/[0.04]'
          )}
        >
          <Icon
            size={20}
            className={selected ? 'text-gold' : 'text-fern'}
            strokeWidth={selected ? 2.5 : 2}
          />
        </div>

        {/* Content */}
        <div className="min-w-0">
          <h3
            className={classNames(
              'text-sm font-semibold mb-0.5',
              selected ? 'text-gold' : 'text-ivory'
            )}
          >
            {title}
          </h3>
          <p className="text-xs text-fern leading-relaxed">{description}</p>
        </div>
      </div>

      {/* Selection indicator */}
      {selected && (
        <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-gold/20 flex items-center justify-center">
          <div className="w-2.5 h-2.5 rounded-full bg-gold" />
        </div>
      )}
    </button>
  );
}
