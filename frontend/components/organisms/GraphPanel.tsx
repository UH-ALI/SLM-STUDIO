'use client';

import { classNames } from '@/lib/utils';
import { TrainingGraph } from '@/components/charts/TrainingGraph';
import type { Metrics } from '@/types/project';

interface GraphPanelProps {
  data: Metrics[];
  className?: string;
}

export function GraphPanel({ data, className }: GraphPanelProps) {
  if (data.length === 0) return null;

  const latest = data[data.length - 1];

  return (
    <div
      className={classNames(
        'glass-card col-span-full',
        className
      )}
    >
      {/* Header */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-ivory">Training Metrics</h3>
        <p className="text-xs text-fern">Performance over training epochs</p>
      </div>

      {/* Chart */}
      <TrainingGraph data={data} className="w-full" />

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-white/[0.06]">
        <div className="bg-[#121B16]/40 rounded-xl p-3">
          <p className="text-[0.65rem] text-muted uppercase tracking-wider mb-1">Train Loss</p>
          <p className="font-mono text-sm font-semibold text-gold">
            {latest.trainLoss != null ? latest.trainLoss.toFixed(4) : '—'}
          </p>
        </div>
        <div className="bg-[#121B16]/40 rounded-xl p-3">
          <p className="text-[0.65rem] text-muted uppercase tracking-wider mb-1">Val Loss</p>
          <p className="font-mono text-sm font-semibold text-mint">
            {latest.valLoss != null ? latest.valLoss.toFixed(4) : '—'}
          </p>
        </div>
        <div className="bg-[#121B16]/40 rounded-xl p-3">
          <p className="text-[0.65rem] text-muted uppercase tracking-wider mb-1">Learning Rate</p>
          <p className="font-mono text-sm font-semibold text-sage">
            {latest.learningRate != null ? latest.learningRate.toExponential(2) : '—'}
          </p>
        </div>
        <div className="bg-[#121B16]/40 rounded-xl p-3">
          <p className="text-[0.65rem] text-muted uppercase tracking-wider mb-1">GPU Util</p>
          <p className="font-mono text-sm font-semibold text-amber">
            {latest.gpuUtil != null ? `${latest.gpuUtil.toFixed(1)}%` : '—'}
          </p>
        </div>
      </div>
    </div>
  );
}
