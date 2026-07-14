'use client';

import { Sprout, Plus } from 'lucide-react';
import { Button } from '@/components/atoms/Button';
import { useRouter } from 'next/navigation';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon: Icon = Sprout,
  title = 'No Projects Yet',
  description = 'Create your first AI assistant by training a model on your own data. It only takes a few minutes to get started.',
  actionLabel = 'Create Your First Project',
  onAction,
  className,
}: EmptyStateProps) {
  const router = useRouter();

  const handleAction = onAction || (() => router.push('/projects/new'));

  return (
    <div
      className={`flex flex-col items-center justify-center text-center py-20 px-6 ${className || ''}`}
    >
      {/* Icon */}
      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-gold/20 to-sage/20 flex items-center justify-center mb-6">
        <Icon size={40} className="text-gold" />
      </div>

      {/* Title */}
      <h3 className="text-xl font-bold text-ivory mb-2">
        {title}
      </h3>

      {/* Description */}
      <p className="text-sm text-fern max-w-sm mb-8 leading-relaxed">
        {description}
      </p>

      {/* CTA */}
      <Button
        icon={Plus}
        onClick={handleAction}
      >
        {actionLabel}
      </Button>
    </div>
  );
}
