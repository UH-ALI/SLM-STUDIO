import { classNames } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface NavItemProps {
  icon: LucideIcon;
  label: string;
  href: string;
  isActive?: boolean;
  isCollapsed?: boolean;
  onClick?: () => void;
}

export function NavItem({
  icon: Icon,
  label,
  isActive = false,
  isCollapsed = false,
  onClick,
}: NavItemProps) {
  return (
    <button
      onClick={onClick}
      className={classNames(
        'w-full flex items-center gap-3 px-3 py-2.5 rounded-button text-sm font-medium transition-all duration-300 ease-brand',
        'focus-visible:outline-2 focus-visible:outline-gold focus-visible:outline-offset-2',
        isActive
          ? 'text-gold bg-gold-soft/[0.08] border-l-[3px] border-l-gold'
          : 'text-fern hover:text-ivory hover:bg-gold-soft/[0.04] border-l-[3px] border-l-transparent',
        isCollapsed && 'justify-center px-2'
      )}
      aria-current={isActive ? 'page' : undefined}
    >
      <Icon
        size={20}
        strokeWidth={isActive ? 2.5 : 2}
        className={classNames(
          'flex-shrink-0 transition-colors',
          isActive ? 'text-gold' : 'text-fern group-hover:text-ivory'
        )}
      />
      {!isCollapsed && (
        <span className="truncate transition-opacity duration-200">
          {label}
        </span>
      )}
    </button>
  );
}
