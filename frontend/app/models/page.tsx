'use client';

import { useEffect } from 'react';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { PageHeader } from '@/components/organisms/PageHeader';
import { ProjectGrid } from '@/components/organisms/ProjectGrid';
import { EmptyState } from '@/components/organisms/EmptyState';
import { Brain } from 'lucide-react';
import { useProjectStore } from '@/stores/projectStore';
import { useUIStore } from '@/stores/uiStore';
import { useRouter } from 'next/navigation';

export default function ModelsPage() {
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
        title="Models"
        subtitle="View and manage your trained AI models"
        showNewProject
      />

      <section>
        {projects.length === 0 && !isLoading ? (
          <EmptyState
            icon={Brain}
            title="No Models Yet"
            description="Create your first AI model by starting a new project and training it on your data."
            actionLabel="Create Your First Model"
            onAction={() => router.push('/projects/new')}
          />
        ) : (
          <ProjectGrid
            projects={projects}
            onProjectAction={handleProjectAction}
          />
        )}
      </section>
    </DashboardLayout>
  );
}
