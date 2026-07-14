import { create } from 'zustand';
import api from '@/lib/api';

export interface WidgetConfig {
  primaryColor: string;
  bodyColor?: string;
  dotsColor?: string;
  botMessageColor?: string;
  userMessageColor?: string;
  chatInputColor?: string;
  position: 'bottom-right' | 'bottom-left';
  greeting: string;
  title?: string | null;
}

export interface DeployConfig {
  isPublic: boolean;
  deployKey: string | null;
  embedScript: string | null;
  publicChatUrl: string | null;
  widgetConfig: WidgetConfig | null;
  allowedOrigins: string[] | null;
  createdAt: string | null;
}

// This endpoint has no Pydantic response_model on the backend (it returns a
// raw list of dicts), so unlike every other endpoint in the app there's no
// camelCase aliasing applied — these are the literal snake_case-free keys
// the handler builds: [{"date": ..., "messages": ...}, ...].
export interface UsageDay {
  date: string;
  messages: number;
}

interface DeployState {
  config: DeployConfig | null;
  usage: UsageDay[];
  isLoading: boolean;
  error: string | null;

  fetchConfig: (projectId: string) => Promise<DeployConfig>;
  enableDeploy: (
    projectId: string,
    data: { isPublic?: boolean; widgetConfig?: Partial<WidgetConfig>; allowedOrigins?: string[] }
  ) => Promise<DeployConfig>;
  disableDeploy: (projectId: string) => Promise<DeployConfig>;
  rotateKey: (projectId: string) => Promise<DeployConfig>;
  fetchUsage: (projectId: string) => Promise<UsageDay[]>;
}

export const useDeployStore = create<DeployState>((set) => ({
  config: null,
  usage: [],
  isLoading: false,
  error: null,

  fetchConfig: async (projectId) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.get(`/projects/${projectId}/deploy`);
      set({ config: response.data, isLoading: false });
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch deployment config';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  enableDeploy: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.post(`/projects/${projectId}/deploy`, data);
      set({ config: response.data, isLoading: false });
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to enable deployment';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  disableDeploy: async (projectId) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.delete(`/projects/${projectId}/deploy`);
      set({ config: response.data, isLoading: false });
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to disable deployment';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  rotateKey: async (projectId) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.post(`/projects/${projectId}/deploy/rotate`);
      set({ config: response.data, isLoading: false });
      return response.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to rotate deploy key';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  fetchUsage: async (projectId) => {
    try {
      const response = await api.get(`/projects/${projectId}/deploy/usage`);
      set({ usage: response.data });
      return response.data;
    } catch (err) {
      // Usage stats are non-critical — fail quietly rather than blocking the panel
      return [];
    }
  },
}));
