import { Bell, Plus } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Button } from '@/components/atoms/Button';
import { useRouter } from 'next/navigation';
import { useUIStore } from '@/stores/uiStore';

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
  const { unreadNotifications, setUnreadNotifications } = useUIStore();

  const handleBellClick = () => {
    setUnreadNotifications(false);
  };

  return (
    <div
      className={classNames(
        'flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between sm:py-6',
        className
      )}
    >
      <div>
        <h1 className="text-[1.5rem] sm:text-[1.75rem] font-bold tracking-[-0.02em] text-ivory">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-fern mt-1">{subtitle}</p>
        )}
      </div>

      <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
        <button
          className={classNames(
            'relative w-10 h-10 rounded-button flex items-center justify-center',
            'bg-[#121B16]/60 border border-white/[0.08] text-fern',
            'hover:text-ivory hover:border-gold/30 transition-all duration-300',
            'focus-visible:outline-2 focus-visible:outline-gold focus-visible:outline-offset-2'
          )}
          aria-label="Notifications"
          onClick={handleBellClick}
        >
          <Bell size={18} />
          {unreadNotifications && (
            <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border border-[#121B16]" />
          )}
        </button>

        {showNewProject && (
          <Button
            icon={Plus}
            className="w-full sm:w-auto"
            onClick={() => router.push('/projects/new')}
          >
            New Project
          </Button>
        )}
      </div>
    </div>
  );
}
