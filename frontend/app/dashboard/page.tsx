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
import { useRouter } from 'next/navigation';

import React, { ErrorInfo } from 'react';

class ErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean, error: Error | null}> {
  constructor(props: {children: React.ReactNode}) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Dashboard caught error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 bg-red-900/50 text-white rounded-lg m-8">
          <h2 className="text-xl font-bold mb-4">Dashboard Render Error</h2>
          <pre className="whitespace-pre-wrap font-mono text-sm">{this.state.error?.toString()}</pre>
          <pre className="whitespace-pre-wrap font-mono text-xs mt-4 text-gray-300">{this.state.error?.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const { projects, isLoading, fetchProjects, deleteProject } = useProjectStore();
  const { addToast } = useUIStore();

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleProjectAction = async (action: string, project: { id: string }) => {
    if (action === 'delete') {
      try {
        await deleteProject(project.id);
        addToast({ type: 'success', message: 'Project deleted successfully' });
      } catch (err) {
        addToast({ type: 'error', message: 'Failed to delete project' });
      }
    } else if (action === 'rename') {
      addToast({ type: 'info', message: 'Rename coming soon' });
    }
  };

  let activities: any[] = [];
  let renderError: Error | null = null;
  try {
    activities = projects.map(p => {
      let activityType = 'info';
      if (p.status === 'completed') activityType = 'success';
      else if (p.status === 'failed') activityType = 'error';
      else if (p.status === 'training') activityType = 'training';
      
      return {
        id: p.id,
        type: activityType,
        message: `Project ${p.name} is ${p.status}`,
        timestamp: p.createdAt || new Date().toISOString(),
      };
    });
  } catch (e) {
    renderError = e instanceof Error ? e : new Error(String(e));
  }

  if (renderError) {
    return (
      <DashboardLayout>
        <div className="p-8 bg-red-900/50 text-white rounded-lg m-8">
          <h2 className="text-xl font-bold mb-4">Dashboard Render Error (Main)</h2>
          <pre className="whitespace-pre-wrap font-mono text-sm">{renderError.toString()}</pre>
          <pre className="whitespace-pre-wrap font-mono text-xs mt-4 text-gray-300">{renderError.stack}</pre>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <ErrorBoundary>
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
        <RecentActivity activities={activities} />
      </section>
      </DashboardLayout>
    </ErrorBoundary>
  );
}
