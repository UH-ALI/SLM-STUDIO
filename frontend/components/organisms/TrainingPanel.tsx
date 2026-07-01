'use client';

import { Badge } from '@/components/atoms/Badge';
import { ProgressBar } from '@/components/atoms/ProgressBar';
import { MetricRow } from '@/components/molecules/MetricRow';
import { TrainingOrb } from '@/components/three/TrainingOrb';
import type { TrainingStatus } from '@/stores/trainingStore';
import type { Metrics } from '@/types/project';
import { classNames } from '@/lib/utils';

interface TrainingPanelProps {
  status: TrainingStatus;
  metrics: Metrics | null;
  progress: number;
  epoch: number;
  className?: string;
}

export function TrainingPanel({
  status,
  metrics,
  progress,
  epoch,
  className,
}: TrainingPanelProps) {
  // 'processing' covers ingestion/data-gen; 'training' is the fine-tuning phase
  // itself (TrainingJob.status can report either while a job is actively running).
  // Treated identically here since both represent "actively running, show live UI".
  const isActive = status === 'processing' || status === 'training';

  const badgeVariant: 'deployed' | 'training' | 'ready' | 'failed' =
    status === 'completed'
      ? 'deployed'
      : isActive
        ? 'training'
        : status === 'failed'
          ? 'failed'
          : 'ready';

  return (
    <div className={classNames('glass-card flex flex-col gap-5', className)}>
      {/* Status badge */}
      <div className="flex items-center justify-between">
        <Badge variant={badgeVariant} pulse={isActive}>
          {isActive ? 'Training' : status}
        </Badge>
        {isActive && (
          <span className="font-mono text-xs text-gold tabular-nums">
            Epoch {epoch}
          </span>
        )}
      </div>

      {/* 3D Orb */}
      <div className="relative w-full aspect-square max-h-[280px]">
        <TrainingOrb
          trainingStatus={status}
          className="absolute inset-0"
        />
        {/* Epoch overlay */}
        {isActive && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
            <span className="font-mono text-2xl font-bold text-gold tabular-nums drop-shadow-lg">
              {epoch}
            </span>
          </div>
        )}
      </div>

      {/* Progress */}
      {isActive && (
        <ProgressBar value={progress} showValue label="Training Progress" />
      )}

      {/* Metrics */}
      <div className="space-y-1 border-t border-white/[0.06] pt-4">
        <MetricRow
          label="Train Loss"
          value={metrics?.trainLoss ?? '—'}
        />
        <MetricRow
          label="Val Loss"
          value={metrics?.valLoss ?? '—'}
        />
        <MetricRow
          label="Learning Rate"
          value={metrics?.learningRate ?? '—'}
        />
        <MetricRow
          label="GPU Util"
          value={metrics?.gpuUtil != null ? `${metrics.gpuUtil.toFixed(1)}%` : '—'}
        />
      </div>
    </div>
  );
}
