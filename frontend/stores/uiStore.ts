import { create } from 'zustand';
import type { Toast } from '@/types/project';

interface UIState {
  sidebarExpanded: boolean;
  theme: 'dark' | 'light';
  toasts: Toast[];
  activeModal: string | null;

  toggleSidebar: () => void;
  setTheme: (theme: 'dark' | 'light') => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  openModal: (modalId: string) => void;
  closeModal: () => void;
}

export const useUIStore = create<UIState>((set, get) => ({
  sidebarExpanded: true,
  theme: 'dark',
  toasts: [],
  activeModal: null,

  toggleSidebar: () => {
    set((state) => ({ sidebarExpanded: !state.sidebarExpanded }));
  },

  setTheme: (theme) => {
    set({ theme });
  },

  addToast: (toast) => {
    const id = 'toast-' + Date.now();
    const newToast: Toast = { ...toast, id };

    set((state) => {
      const toasts = [newToast, ...state.toasts].slice(0, 3);
      return { toasts };
    });

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      get().removeToast(id);
    }, toast.duration || 5000);
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },

  openModal: (modalId) => {
    set({ activeModal: modalId });
  },

  closeModal: () => {
    set({ activeModal: null });
  },
}));
