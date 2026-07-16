'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  GraduationCap,
  Briefcase,
  TrendingUp,
  HeartPulse,
  Scale,
  Globe,
  MoreVertical,
  Clock,
  RotateCcw,
} from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Badge } from '@/components/atoms/Badge';
import { ProgressRing } from '@/components/atoms/ProgressRing';
import type { Project } from '@/types/project';

const useCaseIcons: Record<Project['useCase'], typeof GraduationCap> = {
  education: GraduationCap,
  business: Briefcase,
  finance: TrendingUp,
  medical: HeartPulse,
  legal: Scale,
  general: Globe,
};

const useCaseGradients: Record<Project['useCase'], string> = {
  education: 'from-amber/30 to-gold/20',
  business: 'from-blue-400/30 to-cyan-400/20',
  finance: 'from-emerald-400/30 to-green-400/20',
  medical: 'from-rose/30 to-red-400/20',
  legal: 'from-violet-400/30 to-purple-400/20',
  general: 'from-sage/30 to-mint/20',
};

const useCaseIconColors: Record<Project['useCase'], string> = {
  education: 'text-amber',
  business: 'text-blue-400',
  finance: 'text-emerald-400',
  medical: 'text-rose',
  legal: 'text-violet-400',
  general: 'text-sage',
};

interface ProjectCardProps {
  project: Project;
  onMenuAction?: (action: string, project: Project) => void;
  className?: string;
}

export function ProjectCard({ project, onMenuAction, className }: ProjectCardProps) {
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const Icon = useCaseIcons[project.useCase] || Globe;
  const gradient = useCaseGradients[project.useCase] || 'from-sage/30 to-mint/20';
  const iconColor = useCaseIconColors[project.useCase] || 'text-sage';

  const isDraft = project.status === 'pending';

  const statusVariant: 'deployed' | 'training' | 'ready' | 'failed' =
    isDraft
      ? 'ready'
      : project.status === 'completed'
        ? 'deployed'
        : project.status === 'processing' || project.status === 'training'
          ? 'training'
          : project.status === 'failed'
            ? 'failed'
            : 'ready';

  const handleCardClick = () => {
    if (project.status === 'completed') {
      router.push(`/projects/${project.id}/playground`);
    } else if (isDraft) {
      // Resume the setup wizard where the user left off
      router.push(`/projects/new?resumeId=${project.id}`);
    } else {
      router.push(`/projects/${project.id}/train`);
    }
  };

  const totalEpochs = project.hyperparameters?.epochs || 50;
  const currentEpoch = project.epoch || 0;

  const safeDateStr = (() => {
    try {
      const d = new Date(project.createdAt || Date.now());
      if (isNaN(d.getTime())) return new Date().toLocaleDateString();
      return d.toLocaleDateString();
    } catch {
      return new Date().toLocaleDateString();
    }
  })();

  return (
    <div
      onClick={handleCardClick}
      className={classNames(
        'glass-card group cursor-pointer',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        {/* Icon */}
        <div
          className={classNames(
            'w-11 h-11 rounded-xl bg-gradient-to-br flex items-center justify-center',
            gradient
          )}
        >
          <Icon size={22} className={iconColor} />
        </div>

        {/* Menu */}
        <div className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen(!menuOpen);
            }}
            className={classNames(
              'w-8 h-8 rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100',
              'text-fern hover:text-ivory hover:bg-white/[0.06] transition-all',
              'focus-visible:opacity-100'
            )}
            aria-label="Project menu"
          >
            <MoreVertical size={16} />
          </button>

          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={(e) => { e.stopPropagation(); setMenuOpen(false); }} />
              <div className={classNames(
                'absolute right-0 top-full mt-1 w-40 py-1 rounded-xl z-20',
                'bg-elevated border border-white/[0.08] shadow-glass'
              )}>
                {(project.status === 'failed'
                  ? ['retry', 'rename', 'delete']
                  : ['rename', 'delete']
                ).map((action) => (
                  <button
                    key={action}
                    onClick={(e) => {
                      e.stopPropagation();
                      onMenuAction?.(action, project);
                      setMenuOpen(false);
                    }}
                    className={classNames(
                      'w-full text-left px-3 py-2 text-sm capitalize transition-colors flex items-center gap-2',
                      action === 'delete'
                        ? 'text-rose hover:bg-rose/10'
                        : 'text-ivory/80 hover:bg-white/[0.04]'
                    )}
                  >
                    {action === 'retry' && <RotateCcw size={14} />}
                    {action}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Name — Bug 1 fix: show project.name instead of project.modelName */}
      <h3 className="text-sm font-semibold text-ivory mb-1 truncate">{project.name}</h3>

      {/* Status */}
      <div className="flex items-center gap-2 mb-4">
        <Badge variant={statusVariant} pulse={project.status === 'processing' || project.status === 'training'}>
          {isDraft ? 'draft' : project.status}
        </Badge>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
        {project.status === 'processing' ? (
          <div className="flex items-center gap-2">
            <ProgressRing value={currentEpoch} max={totalEpochs} size={28} />
            <span className="text-xs text-fern">
              Epoch {currentEpoch}/{totalEpochs}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs text-muted">
            <Clock size={12} />
            <span>{safeDateStr}</span>
          </div>
        )}

        <span className="text-[0.65rem] text-muted bg-white/[0.04] px-2 py-0.5 rounded-full">
          v1
        </span>
      </div>
    </div>
  );
}
