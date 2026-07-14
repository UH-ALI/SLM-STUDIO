import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    // [FIX] ngrok's free tier serves an HTML "browser warning" splash page
    // to any request that looks like it's from a real browser, intercepting
    // it before your FastAPI backend ever sees it. That splash page has no
    // CORS headers, which looks identical to a backend CORS misconfiguration
    // from the browser's point of view. This header bypasses it — has no
    // effect at all once you're off ngrok (e.g. on Vast.ai + Cloudflare Tunnel).
    'ngrok-skip-browser-warning': 'true',
  },
});

// Request interceptor: attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('slm_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('slm_token');
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
