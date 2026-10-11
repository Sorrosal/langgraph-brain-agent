import { AxiosError } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api-error';
import { api, configureApi } from '../axios-instance';

interface StubReply {
  status: number;
  data?: unknown;
  headers?: Record<string, string>;
}

function stubServer(handler: (config: InternalAxiosRequestConfig) => StubReply) {
  const calls: InternalAxiosRequestConfig[] = [];
  api.defaults.adapter = (config) => {
    calls.push(config);
    const { status, data = {}, headers = {} } = handler(config);
    const response: AxiosResponse = { status, statusText: '', data, headers, config };
    if (status < 400) return Promise.resolve(response);
    const error = new AxiosError(
      `Request failed with status code ${String(status)}`,
      AxiosError.ERR_BAD_REQUEST,
      config,
      null,
      response,
    );
    return Promise.reject(error);
  };
  return calls;
}

function envelope(code: string, message: string, requestId?: string) {
  return { error: { code, message, ...(requestId ? { request_id: requestId } : {}) } };
}

async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ApiError) return error;
    throw error;
  }
  throw new Error('Expected the request to be rejected');
}

describe('axios instance', () => {
  const onUnauthorized = vi.fn();

  beforeEach(() => {
    onUnauthorized.mockReset();
    configureApi({ getToken: () => 'tok-123', onUnauthorized });
  });

  it('attaches the bearer token', async () => {
    const calls = stubServer(() => ({ status: 200 }));
    await api.get('/threads');
    expect(calls[0]?.headers.Authorization).toBe('Bearer tok-123');
  });

  it('omits the Authorization header without a token', async () => {
    configureApi({ getToken: () => null, onUnauthorized });
    const calls = stubServer(() => ({ status: 200 }));
    await api.get('/threads');
    expect(calls[0]?.headers.Authorization).toBeUndefined();
  });

  it('signs the user out on 401 from a regular endpoint, without retrying', async () => {
    const calls = stubServer(() => ({
      status: 401,
      data: envelope('unauthorized', 'Invalid or expired token'),
    }));
    const error = await rejection(api.get('/threads'));
    expect(error.status).toBe(401);
    expect(error.message).toBe('Invalid or expired token');
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(calls).toHaveLength(1);
  });

  it.each(['/auth/login', '/auth/register'])(
    'rejects a typed ApiError on 401 from %s without signing out',
    async (path) => {
      stubServer(() => ({
        status: 401,
        data: envelope('unauthorized', 'Invalid email or password'),
      }));
      const error = await rejection(api.post(path, {}));
      expect(error.status).toBe(401);
      expect(error.code).toBe('unauthorized');
      expect(error.message).toBe('Invalid email or password');
      expect(onUnauthorized).not.toHaveBeenCalled();
    },
  );

  it('falls back to a fixed message for a bare 401 from login', async () => {
    stubServer(() => ({ status: 401 }));
    const error = await rejection(api.post('/auth/login', {}));
    expect(error.message).toBe('Invalid email or password');
  });

  it('parses the backend error envelope', async () => {
    stubServer(() => ({ status: 500, data: envelope('internal_error', 'Boom', 'req-9') }));
    const error = await rejection(api.get('/threads'));
    expect(error).toMatchObject({
      status: 500,
      code: 'internal_error',
      message: 'Boom',
      requestId: 'req-9',
    });
  });

  it('exposes Retry-After as seconds on 429', async () => {
    stubServer(() => ({
      status: 429,
      data: envelope('rate_limited', 'Too many requests; slow down.'),
      headers: { 'retry-after': '7' },
    }));
    const error = await rejection(api.post('/threads/t/messages', {}));
    expect(error.status).toBe(429);
    expect(error.retryAfter).toBe(7);
  });

  it('handles bodies that are not an envelope', async () => {
    stubServer(() => ({ status: 502, data: '<html>bad gateway</html>' }));
    const error = await rejection(api.get('/threads'));
    expect(error.status).toBe(502);
    expect(error.code).toBeUndefined();
    expect(error.message).toContain('502');
  });
});
