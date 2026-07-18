import { ActivityFeed } from './ActivityFeed';
import type { Activity } from '@/types/project';

interface RecentActivityProps {
  activities: Activity[];
  className?: string;
}

export function RecentActivity({ activities, className }: RecentActivityProps) {
  return (
    <section className={className}>
      <h2 className="text-[0.75rem] font-semibold uppercase tracking-[0.08em] text-fern mb-4">
        RECENT ACTIVITY
      </h2>
      <ActivityFeed activities={activities} />
    </section>
  );
}
