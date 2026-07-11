import { classNames } from '@/lib/utils';
import type { LogEntry as LogEntryType } from '@/types/project';

interface LogEntryProps {
  log: LogEntryType;
  className?: string;
}

const levelColors: Record<LogEntryType['level'], string> = {
  info: 'text-sage bg-sage/10 border-sage/20',
  warn: 'text-amber bg-amber/10 border-amber/20',
  error: 'text-rose bg-rose/10 border-rose/20',
  success: 'text-mint bg-mint/10 border-mint/20',
};

const levelLabels: Record<LogEntryType['level'], string> = {
  info: 'INFO',
  warn: 'WARN',
  error: 'ERROR',
  success: 'OK',
};

export function LogEntry({ log, className }: LogEntryProps) {
  const rawTime = log.createdAt || log.time;
  const time = rawTime
    ? new Date(rawTime).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
    : '--:--:--';

  return (
    <div
      className={classNames(
        'flex items-start gap-2.5 py-1 font-mono text-[0.78rem] leading-relaxed',
        className
      )}
    >
      {/* Timestamp */}
      <span className="text-muted tabular-nums flex-shrink-0">{time}</span>

      {/* Level badge */}
      <span
        className={classNames(
          'flex-shrink-0 px-1.5 py-0.5 rounded text-[0.65rem] font-bold border leading-none mt-0.5',
          levelColors[log.level]
        )}
      >
        {levelLabels[log.level]}
      </span>

      {/* Message */}
      <span
        className={classNames(
          'break-all',
          log.level === 'error' && 'text-rose',
          log.level === 'warn' && 'text-amber',
          log.level === 'success' && 'text-mint',
          log.level === 'info' && 'text-fern/80'
        )}
      >
        {log.message}
      </span>
    </div>
  );
}
