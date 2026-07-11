import { classNames } from '@/lib/utils';
import { ProjectCard } from './ProjectCard';
import { NewProjectCard } from './NewProjectCard';
import type { Project } from '@/types/project';

interface ProjectGridProps {
  projects: Project[];
  onProjectAction?: (action: string, project: Project) => void;
  className?: string;
}

export function ProjectGrid({ projects, onProjectAction, className }: ProjectGridProps) {
  return (
    <div
      className={classNames(
        'grid gap-4',
        'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
        className
      )}
    >
      <NewProjectCard />
      {projects.map((project) => (
        <ProjectCard
          key={project.id}
          project={project}
          onMenuAction={onProjectAction}
        />
      ))}
    </div>
  );
}
