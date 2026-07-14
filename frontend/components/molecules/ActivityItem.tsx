import { classNames } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/utils';

type ActivityType = 'success' | 'training' | 'info' | 'error';

interface ActivityItemProps {
  type: ActivityType;
  message: string;
  timestamp: string;
}

const typeColors: Record<ActivityType, string> = {
  success: 'bg-mint',
  training: 'bg-gold',
  info: 'bg-sage',
  error: 'bg-rose',
};

export function ActivityItem({ type, message, timestamp }: ActivityItemProps) {
  return (
    <div className="flex items-start gap-3 min-w-0 flex-shrink-0">
      {/* Dot */}
      <div className="flex-shrink-0 mt-1.5">
        <span
          className={classNames(
            'block w-2 h-2 rounded-full',
            typeColors[type],
            type === 'training' && 'animate-pulse'
          )}
        />
      </div>

      {/* Content */}
      <div className="min-w-0">
        <p className="text-sm text-ivory/80 truncate max-w-[200px]">{message}</p>
        <time className="text-xs text-muted tabular-nums">
          {formatRelativeTime(timestamp)}
        </time>
      </div>
    </div>
  );
}
