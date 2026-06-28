'use client';

import { useEffect } from 'react';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { PageHeader } from '@/components/organisms/PageHeader';
import { ProjectGrid } from '@/components/organisms/ProjectGrid';
import { RecentActivity } from '@/components/organisms/RecentActivity';
import { EmptyState } from '@/components/organisms/EmptyState';
import { Sprout } from 'lucide-react';
import { useProjectStore } from '@/stores/projectStore';
import { useUIStore } from '@/stores/uiStore';
import { mockActivities } from '@/mocks/data';
import { useRouter } from 'next/navigation';

export default function DashboardPage() {
  const router = useRouter();
  const { projects, isLoading, fetchProjects } = useProjectStore();
  const { addToast } = useUIStore();

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleProjectAction = (action: string, _project: { id: string }) => {
    if (action === 'delete') {
      addToast({ type: 'info', message: 'Project deleted' });
    } else if (action === 'rename') {
      addToast({ type: 'info', message: 'Rename coming soon' });
    } else if (action === 'duplicate') {
      addToast({ type: 'info', message: 'Project duplicated' });
    }
  };

  return (
    <DashboardLayout>
      <PageHeader
        title="Dashboard"
        subtitle="Manage your AI assistants"
        showNewProject
      />

      {/* CRITICAL: ProjectsSection FIRST (top), RecentActivity SECOND (below) */}
      <section className="mb-10">
        {projects.length === 0 && !isLoading ? (
          <EmptyState
            icon={Sprout}
            title="No Projects Yet"
            description="Create your first AI assistant by training a model on your own data."
            actionLabel="Create Your First Project"
            onAction={() => router.push('/projects/new')}
          />
        ) : (
          <ProjectGrid
            projects={projects}
            onProjectAction={handleProjectAction}
          />
        )}
      </section>

      <section>
        <RecentActivity activities={mockActivities} />
      </section>
    </DashboardLayout>
  );
}
