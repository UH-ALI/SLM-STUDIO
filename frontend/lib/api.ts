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

// [FEATURE] Silent access-token refresh. When the access token expires
// mid-session, a single shared refresh call is made (concurrent 401s all
// await the same in-flight promise instead of each firing their own
// /auth/refresh) and the failed request is retried once with the new token.
// Falls back to the existing hard-redirect-to-login behavior if the refresh
// token is missing, invalid, or itself expired.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('slm_refresh_token');
  if (!refreshToken) return null;

  try {
    const response = await axios.post(
      `${api.defaults.baseURL}/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'ngrok-skip-browser-warning': 'true' } }
    );
    const { access_token, refresh_token: newRefreshToken } = response.data;
    localStorage.setItem('slm_token', access_token);
    if (newRefreshToken) {
      localStorage.setItem('slm_refresh_token', newRefreshToken);
    }
    return access_token;
  } catch {
    return null;
  }
}

// Response interceptor: handle 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest?._retry) {
      if (originalRequest) originalRequest._retry = true;

      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const newAccessToken = await refreshPromise;

      if (newAccessToken && originalRequest) {
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      }

      // Refresh failed (no refresh token, expired, or revoked) — same
      // fallback as before: clear the session and bounce to login.
      localStorage.removeItem('slm_token');
      localStorage.removeItem('slm_refresh_token');
      localStorage.removeItem('slm_user');
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
