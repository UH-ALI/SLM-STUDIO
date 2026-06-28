import { create } from 'zustand';
import api from '@/lib/api';
import type { Project, Dataset, FewShotExample, Hyperparameters } from '@/types/project';

interface ProjectState {
  projects: Project[];
  activeProject: Project | null;
  datasets: Dataset[];
  isLoading: boolean;
  error: string | null;

  fetchProjects: () => Promise<void>;
  fetchProject: (projectId: string) => Promise<Project>;
  setActiveProject: (project: Project | null) => void;

  // Step 1 — create the Project shell (name/useCase/persona/fewShot only).
  createProject: (data: {
    name: string;
    useCase: string;
    persona: string;
    fewShotExamples?: FewShotExample[];
  }) => Promise<Project>;

  // Step 2 — upload one or more files and link them to the project.
  uploadDatasets: (projectId: string, files: File[]) => Promise<Dataset[]>;

  // Step 3 — kick off training with the chosen base model + hyperparameters.
  // `temperature` is sent separately as inferenceTemperature, matching the
  // backend's ProjectTrainRequest schema (it isn't nested under hyperparameters
  // server-side even though the wizard UI nests it there for convenience).
  startTraining: (
    projectId: string,
    data: {
      baseModelName: string;
      hyperparameters: Hyperparameters;
    }
  ) => Promise<Project>;

  fetchDatasets: () => Promise<void>;
}

export const useProjectStore = create<ProjectState>((set) => ({
  projects: [],
  activeProject: null,
  datasets: [],
  isLoading: false,
  error: null,

  fetchProjects: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/projects');
      set({ projects: response.data, isLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch projects';
      set({ error: message, isLoading: false });
    }
  },

  fetchProject: async (projectId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get(`/projects/${projectId}`);
      const project = response.data;
      set((state) => ({
        activeProject: project,
        projects: state.projects.some((p) => p.id === project.id)
          ? state.projects.map((p) => (p.id === project.id ? project : p))
          : [...state.projects, project],
        isLoading: false,
      }));
      return project;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch project';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  setActiveProject: (project) => {
    set({ activeProject: project });
  },

  createProject: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.post('/projects', data);
      const newProject = response.data;
      set((state) => ({
        projects: [...state.projects, newProject],
        activeProject: newProject,
        isLoading: false,
      }));
      return newProject;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create project';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  uploadDatasets: async (projectId, files) => {
    set({ isLoading: true, error: null });
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));

      const response = await api.post(`/projects/${projectId}/datasets`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const newDatasets: Dataset[] = response.data;
      set((state) => ({
        datasets: [...state.datasets, ...newDatasets],
        isLoading: false,
      }));
      return newDatasets;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to upload datasets';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  startTraining: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const { temperature, ...restHyperparameters } = data.hyperparameters;
      const response = await api.post(`/projects/${projectId}/train`, {
        baseModelName: data.baseModelName,
        hyperparameters: restHyperparameters,
        inferenceTemperature: temperature ?? 0.3,
      });
      const updatedProject = response.data;
      set((state) => ({
        activeProject: updatedProject,
        projects: state.projects.map((p) => (p.id === projectId ? updatedProject : p)),
        isLoading: false,
      }));
      return updatedProject;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start training';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  fetchDatasets: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get('/datasets');
      set({ datasets: response.data, isLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch datasets';
      set({ error: message, isLoading: false });
    }
  },
}));
