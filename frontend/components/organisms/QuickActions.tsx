'use client';

import { Plus, Upload, Brain } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { classNames } from '@/lib/utils';

interface QuickActionsProps {
  className?: string;
}

export function QuickActions({ className }: QuickActionsProps) {
  const router = useRouter();

  const actions = [
    {
      label: 'New Project',
      icon: Plus,
      onClick: () => router.push('/projects/new'),
      gradient: 'from-gold/20 to-amber/20',
      iconColor: 'text-gold',
    },
    {
      label: 'Upload Dataset',
      icon: Upload,
      onClick: () => router.push('/datasets'),
      gradient: 'from-sage/20 to-mint/20',
      iconColor: 'text-sage',
    },
    {
      label: 'Train Model',
      icon: Brain,
      onClick: () => router.push('/projects/new'),
      gradient: 'from-mint/20 to-gold/20',
      iconColor: 'text-mint',
    },
  ];

  return (
    <div className={className}>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.label}
              onClick={action.onClick}
              className={classNames(
                'flex w-full items-center gap-2 px-4 py-2.5 rounded-button sm:w-auto',
                'bg-gradient-to-br border border-white/[0.06]',
                'hover:scale-[1.02] hover:border-gold/20 transition-all duration-300',
                'focus-visible:outline-2 focus-visible:outline-gold',
                action.gradient
              )}
            >
              <Icon size={16} className={action.iconColor} />
              <span className="text-xs font-medium text-ivory">{action.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
