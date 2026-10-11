import axios from 'axios';
import { env } from '@/shared/config/env';
import { ApiError, parseApiError } from './api-error';

/**
 * The backend issues access tokens only (no refresh), so the transport just attaches the token
 * and reports 401s. Who owns the session is decided by the app layer through `configureApi`.
 */
export interface ApiAuthBridge {
  getToken: () => string | null;
  /** Called on a 401 from any endpoint except login/register. */
  onUnauthorized: () => void;
}

let bridge: ApiAuthBridge = { getToken: () => null, onUnauthorized: () => undefined };

export function configureApi(next: ApiAuthBridge): void {
  bridge = next;
}

export function getAccessToken(): string | null {
  return bridge.getToken();
}

const CREDENTIAL_PATHS = ['/auth/login', '/auth/register'];
const INVALID_CREDENTIALS = 'Invalid email or password';

function isCredentialRequest(url: string | undefined): boolean {
  return CREDENTIAL_PATHS.some((path) => url?.endsWith(path) === true);
}

export const api = axios.create({
  baseURL: env.VITE_API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const token = bridge.getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(undefined, (error: unknown) => {
  if (!axios.isAxiosError(error)) {
    return Promise.reject(new ApiError('An unexpected error occurred', 0));
  }
  const status = error.response?.status ?? 0;
  const credentialRequest = isCredentialRequest(error.config?.url);
  if (status === 401 && !credentialRequest) bridge.onUnauthorized();

  const fallback =
    status === 401 && credentialRequest
      ? INVALID_CREDENTIALS
      : status === 0
        ? 'Unable to reach the server'
        : `Request failed with status ${String(status)}`;
  const retryAfter: unknown = error.response?.headers['retry-after'];
  return Promise.reject(
    parseApiError(
      status,
      error.response?.data,
      fallback,
      typeof retryAfter === 'string' ? retryAfter : undefined,
    ),
  );
});
