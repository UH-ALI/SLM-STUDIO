import { classNames } from '@/lib/utils';

interface DividerProps {
  direction?: 'horizontal' | 'vertical';
  strength?: 'subtle' | 'strong';
  className?: string;
  label?: string;
}

export function Divider({
  direction = 'horizontal',
  strength = 'subtle',
  className,
  label,
}: DividerProps) {
  const isHorizontal = direction === 'horizontal';

  return (
    <div
      className={classNames(
        'flex items-center',
        isHorizontal ? 'w-full' : 'h-full flex-col',
        className
      )}
      role="separator"
    >
      <div
        className={classNames(
          isHorizontal ? 'flex-1 h-px' : 'w-px flex-1',
          strength === 'subtle' ? 'bg-white/[0.06]' : 'bg-white/[0.12]'
        )}
      />
      {label && (
        <span
          className={classNames(
            'text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-muted',
            isHorizontal ? 'px-3' : 'py-2'
          )}
        >
          {label}
        </span>
      )}
      {label && (
        <div
          className={classNames(
            isHorizontal ? 'flex-1 h-px' : 'w-px flex-1',
            strength === 'subtle' ? 'bg-white/[0.06]' : 'bg-white/[0.12]'
          )}
        />
      )}
    </div>
  );
}
