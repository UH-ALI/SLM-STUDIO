'use client';

import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { PageHeader } from '@/components/organisms/PageHeader';
import { ProjectGrid } from '@/components/organisms/ProjectGrid';
import { EmptyState } from '@/components/organisms/EmptyState';
import { RenameProjectModal } from '@/components/organisms/RenameProjectModal';
import { Brain } from 'lucide-react';
import { useProjectStore } from '@/stores/projectStore';
import { useUIStore } from '@/stores/uiStore';
import { useRouter } from 'next/navigation';

export default function ModelsPage() {
  const router = useRouter();
  const { projects, isLoading, fetchProjects, deleteProject, renameProject } = useProjectStore();
  const { addToast } = useUIStore();
  const [renamingProject, setRenamingProject] = useState<{ id: string; name: string } | null>(null);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleProjectAction = async (action: string, project: { id: string; name?: string }) => {
    if (action === 'delete') {
      try {
        await deleteProject(project.id);
        addToast({ type: 'success', message: 'Project deleted successfully' });
      } catch (err) {
        addToast({ type: 'error', message: 'Failed to delete project' });
      }
    } else if (action === 'rename') {
      setRenamingProject({ id: project.id, name: project.name || '' });
    }
  };

  const handleRenameSubmit = async (newName: string) => {
    if (!renamingProject) return;
    try {
      await renameProject(renamingProject.id, newName);
      addToast({ type: 'success', message: 'Project renamed' });
    } catch (err) {
      addToast({ type: 'error', message: 'Failed to rename project' });
    } finally {
      setRenamingProject(null);
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

      {renamingProject && (
        <RenameProjectModal
          currentName={renamingProject.name}
          onCancel={() => setRenamingProject(null)}
          onSubmit={handleRenameSubmit}
        />
      )}
    </DashboardLayout>
  );
}
