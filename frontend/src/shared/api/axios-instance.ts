import axios from 'axios';
import { ApiError } from './api-error';

// Avoid circular dependency: import store lazily
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: string) => void;
  reject: (reason: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else if (token) {
      resolve(token);
    }
  });
  failedQueue = [];
}

export const api = axios.create({
  baseURL: (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:3000/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Request interceptor: inject Bearer token
api.interceptors.request.use(
  (config) => {
    // Import dynamically to avoid circular dependency
    const stored = localStorage.getItem('auth-store');
    if (stored) {
      const parsed = JSON.parse(stored) as { state?: { token?: string | null } };
      const token = parsed.state?.token;
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error: unknown) => Promise.reject(error instanceof Error ? error : new Error(String(error))),
);

// Response interceptor: handle 401 → refresh → retry
api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) {
      return Promise.reject(new ApiError('An unexpected error occurred', 0));
    }

    const originalRequest = error.config;
    const status = error.response?.status;

    // Transform to typed ApiError
    const apiError = new ApiError(
      (error.response?.data as { message?: string } | undefined)?.message ?? error.message,
      status ?? 0,
      error.response?.data as { message: string; code?: string } | undefined,
    );

    if (status === 401 && originalRequest && !('_retry' in originalRequest)) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      (originalRequest as typeof originalRequest & { _retry: boolean })._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = localStorage.getItem('refresh-token');
        if (!refreshToken) throw new Error('No refresh token');

        const { data } = await axios.post<{ token: string }>(
          `${(import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:3000/api'}/auth/refresh`,
          { refreshToken },
        );

        const stored = localStorage.getItem('auth-store');
        if (stored) {
          const parsed = JSON.parse(stored) as { state?: Record<string, unknown> };
          if (parsed.state) {
            parsed.state.token = data.token;
            localStorage.setItem('auth-store', JSON.stringify(parsed));
          }
        }

        processQueue(null, data.token);
        originalRequest.headers.Authorization = `Bearer ${data.token}`;
        return await api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('auth-store');
        window.location.href = '/login';
        const err = refreshError instanceof Error ? refreshError : new Error(String(refreshError));
        return await Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(apiError);
  },
);
