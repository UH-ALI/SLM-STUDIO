import { create } from 'zustand';
import type { Metrics, LogEntry } from '@/types/project';

export type TrainingStatus = 'idle' | 'pending' | 'processing' | 'training' | 'completed' | 'failed';

interface TrainingState {
  status: TrainingStatus;
  metrics: Metrics | null;
  logs: LogEntry[];
  progress: number;
  epoch: number;
  history: Metrics[];

  setStatus: (status: TrainingStatus) => void;
  updateMetrics: (metrics: Metrics) => void;
  addLog: (log: LogEntry) => void;
  setLogs: (logs: LogEntry[]) => void;
  setHistory: (history: Metrics[]) => void;
  setProgress: (progress: number) => void;
  setEpoch: (epoch: number) => void;
  reset: () => void;
}

const initialState = {
  status: 'idle' as TrainingStatus,
  metrics: null,
  logs: [],
  progress: 0,
  epoch: 0,
  history: [],
};

export const useTrainingStore = create<TrainingState>((set) => ({
  ...initialState,

  setStatus: (status) => set({ status }),

  updateMetrics: (metrics) =>
    set((state) => ({
      metrics,
      history: [...state.history, metrics],
    })),

  addLog: (log) =>
    set((state) => ({
      logs: [...state.logs, log].slice(-100),
    })),

  setLogs: (logs) => set({ logs }),

  setHistory: (history) => set({ history }),

  setProgress: (progress) => set({ progress }),

  setEpoch: (epoch) => set({ epoch }),

  reset: () => set(initialState),
}));
