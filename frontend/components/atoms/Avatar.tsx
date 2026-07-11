import { classNames } from '@/lib/utils';

type AvatarSize = 'sm' | 'md' | 'lg';

interface AvatarProps {
  src?: string;
  alt?: string;
  name?: string;
  size?: AvatarSize;
  className?: string;
}

const sizeClasses: Record<AvatarSize, string> = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-14 h-14 text-base',
};

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function Avatar({ src, alt, name = '', size = 'md', className }: AvatarProps) {
  const initials = getInitials(name);

  if (src) {
    return (
      <img
        src={src}
        alt={alt || name}
        className={classNames(
          'rounded-full object-cover ring-2 ring-white/[0.06]',
          sizeClasses[size],
          className
        )}
      />
    );
  }

  return (
    <div
      className={classNames(
        'rounded-full flex items-center justify-center font-semibold text-void',
        'bg-gradient-to-br from-gold via-sage to-mint',
        sizeClasses[size],
        className
      )}
      role="img"
      aria-label={alt || name}
    >
      {initials}
    </div>
  );
}
