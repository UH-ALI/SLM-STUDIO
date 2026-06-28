import { useRef } from 'react';
import { ActivityItem } from '@/components/molecules/ActivityItem';
import type { Activity } from '@/types/project';

interface ActivityFeedProps {
  activities: Activity[];
  className?: string;
}

export function ActivityFeed({ activities, className }: ActivityFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={scrollRef}
      className={`flex gap-6 overflow-x-auto pb-2 px-1 scrollbar-thin ${className}`}
    >
      {activities.map((activity) => (
        <div key={activity.id} className="flex-shrink-0 w-[240px]">
          <ActivityItem
            type={activity.type}
            message={activity.message}
            timestamp={activity.timestamp}
          />
        </div>
      ))}
    </div>
  );
}
