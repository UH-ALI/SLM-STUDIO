import { forwardRef } from 'react';
import { classNames } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'icon';
type ButtonSize = 'sm' | 'md';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: LucideIcon;
  iconPosition?: 'left' | 'right';
  isLoading?: boolean;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      icon: Icon,
      iconPosition = 'left',
      isLoading = false,
      fullWidth = false,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    const baseClasses =
      'relative inline-flex items-center justify-center gap-2 rounded-button font-semibold transition-all duration-300 ease-brand focus-visible:outline-2 focus-visible:outline-gold focus-visible:outline-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

    const sizeClasses: Record<ButtonSize, string> = {
      sm: 'text-[0.8125rem] px-3 py-1.5',
      md: 'text-[0.875rem] px-4 py-2.5',
    };

    const iconSize = size === 'sm' ? 14 : 18;

    const variantClasses: Record<ButtonVariant, string> = {
      primary: 'btn-primary text-void',
      secondary:
        'bg-transparent border border-white/[0.06] text-ivory hover:border-gold/40 hover:bg-gold-soft/10',
      ghost: 'bg-transparent text-fern hover:text-ivory hover:bg-white/[0.04]',
      danger: 'bg-rose/10 border border-rose/20 text-rose hover:bg-rose/20',
      icon: 'p-2 rounded-[10px] text-fern hover:text-ivory hover:bg-white/[0.04]',
    };

    return (
      <button
        ref={ref}
        className={classNames(
          baseClasses,
          sizeClasses[size],
          variantClasses[variant],
          fullWidth && 'w-full',
          className
        )}
        disabled={disabled || isLoading}
        aria-busy={isLoading}
        {...props}
      >
        {isLoading && (
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
        )}
        {!isLoading && Icon && iconPosition === 'left' && (
          <Icon size={iconSize} strokeWidth={2} />
        )}
        {children}
        {!isLoading && Icon && iconPosition === 'right' && (
          <Icon size={iconSize} strokeWidth={2} />
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
