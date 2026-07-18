import { create } from 'zustand';
import api from '@/lib/api';
import type { User } from '@/types/project';

type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'unauthenticated' | 'error';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  status: AuthStatus;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  initialize: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  status: 'idle',
  error: null,

  initialize: () => {
    const token = localStorage.getItem('slm_token');
    const storedUser = localStorage.getItem('slm_user');
    if (token) {
      // Restore user from localStorage first so profile shows correctly on refresh
      const user = storedUser ? JSON.parse(storedUser) : null;
      set({ token, status: 'authenticated', isAuthenticated: true, user });
      // Still fetch fresh profile from API in case anything changed
      api.get('/users/me')
        .then((res) => {
          localStorage.setItem('slm_user', JSON.stringify(res.data));
          set({ user: res.data, status: 'authenticated', isAuthenticated: true });
        })
        .catch(() => {
          // Note: a 401 here is already handled by api.ts's response
          // interceptor, which tries a silent refresh before this .catch
          // ever fires — so landing here means refresh also failed.
          localStorage.removeItem('slm_token');
          localStorage.removeItem('slm_refresh_token');
          localStorage.removeItem('slm_user');
          set({ user: null, token: null, status: 'unauthenticated', isAuthenticated: false });
        });
    } else {
      set({ status: 'unauthenticated' });
    }
  },

  login: async (email: string, password: string) => {
    set({ status: 'loading', error: null });
    try {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await api.post('/auth/login', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const { access_token, refresh_token, user } = response.data;
      localStorage.setItem('slm_token', access_token);
      if (refresh_token) {
        localStorage.setItem('slm_refresh_token', refresh_token);
      }
      // Save the user object so refresh restores the correct profile
      localStorage.setItem('slm_user', JSON.stringify(user));

      set({
        token: access_token,
        user,
        isAuthenticated: true,
        status: 'authenticated',
        error: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      set({ status: 'error', error: message });
      throw err;
    }
  },

  logout: () => {
    // Best-effort server-side revoke — the local session is cleared either way.
    const refreshToken = localStorage.getItem('slm_refresh_token');
    if (refreshToken) {
      api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => {});
    }
    localStorage.removeItem('slm_token');
    localStorage.removeItem('slm_refresh_token');
    localStorage.removeItem('slm_user');
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      status: 'unauthenticated',
      error: null,
    });
  },

  setUser: (user: User) => {
    set({ user });
  },
}));
