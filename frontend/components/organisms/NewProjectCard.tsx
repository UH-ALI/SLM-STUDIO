import { Plus } from 'lucide-react';
import { classNames } from '@/lib/utils';
import { useRouter } from 'next/navigation';

interface NewProjectCardProps {
  className?: string;
}

export function NewProjectCard({ className }: NewProjectCardProps) {
  const router = useRouter();

  return (
    <button
      onClick={() => router.push('/projects/new')}
      className={classNames(
        'relative w-full h-full min-h-[200px] rounded-card border-2 border-dashed border-white/[0.08]',
        'bg-transparent backdrop-blur-sm',
        'flex flex-col items-center justify-center gap-3',
        'transition-all duration-400 ease-brand',
        'hover:border-gold/40 hover:bg-gold/[0.03]',
        'focus-visible:outline-2 focus-visible:outline-gold focus-visible:outline-offset-2',
        'group cursor-pointer',
        className
      )}
    >
      {/* Plus icon */}
      <div
        className={classNames(
          'w-14 h-14 rounded-2xl bg-gradient-to-br from-gold/20 to-sage/20',
          'flex items-center justify-center transition-transform duration-400',
          'group-hover:rotate-90'
        )}
      >
        <Plus size={28} className="text-gold" />
      </div>

      <span className="text-sm font-medium text-fern group-hover:text-gold transition-colors">
        Create New Project
      </span>
    </button>
  );
}
