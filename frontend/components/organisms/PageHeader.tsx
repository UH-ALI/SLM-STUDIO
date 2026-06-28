import { Bell, Plus } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Button } from '@/components/atoms/Button';
import { useRouter } from 'next/navigation';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  showNewProject?: boolean;
  className?: string;
}

export function PageHeader({
  title,
  subtitle,
  showNewProject = false,
  className,
}: PageHeaderProps) {
  const router = useRouter();

  return (
    <div
      className={classNames(
        'flex items-center justify-between py-6',
        className
      )}
    >
      <div>
        <h1 className="text-[1.75rem] font-bold tracking-[-0.02em] text-ivory">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-fern mt-1">{subtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          className={classNames(
            'w-10 h-10 rounded-button flex items-center justify-center',
            'bg-[#121B16]/60 border border-white/[0.08] text-fern',
            'hover:text-ivory hover:border-gold/30 transition-all duration-300',
            'focus-visible:outline-2 focus-visible:outline-gold focus-visible:outline-offset-2'
          )}
          aria-label="Notifications"
        >
          <Bell size={18} />
        </button>

        {showNewProject && (
          <Button
            icon={Plus}
            onClick={() => router.push('/projects/new')}
          >
            New Project
          </Button>
        )}
      </div>
    </div>
  );
}
