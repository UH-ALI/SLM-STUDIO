'use client';

import { useEffect, useRef } from 'react';
import { classNames } from '@/lib/utils';
import { LogEntry } from '@/components/molecules/LogEntry';
import type { LogEntry as LogEntryType } from '@/types/project';
import type { TrainingStatus } from '@/stores/trainingStore';

interface LogPanelProps {
  logs: LogEntryType[];
  status: TrainingStatus;
  className?: string;
}

export function LogPanel({ logs, status, className }: LogPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const isTraining = status === 'processing' || status === 'training';

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div
      className={classNames(
        'glass-card flex flex-col h-full',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/[0.06] mb-3">
        <h3 className="text-sm font-semibold text-ivory">Training Logs</h3>
        {isTraining && (
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-gold animate-pulse" />
            <span className="text-xs text-gold">LIVE</span>
          </div>
        )}
      </div>

      {/* Log entries */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-0.5 max-h-[400px] scrollbar-thin pr-2"
      >
        {logs.length === 0 ? (
          <p className="text-sm text-muted text-center py-8">No logs yet</p>
        ) : (
          logs.slice(-20).map((log, index) => (
            <LogEntry key={index} log={log} />
          ))
        )}
      </div>
    </div>
  );
}
