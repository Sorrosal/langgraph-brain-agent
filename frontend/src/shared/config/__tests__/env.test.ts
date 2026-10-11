import { describe, expect, it } from 'vitest';
import { parseEnv } from '../env';

describe('parseEnv', () => {
  it('applies the defaults in development', () => {
    expect(parseEnv({}, true)).toEqual({
      VITE_API_URL: 'http://localhost:8000',
      VITE_APP_NAME: 'Brain Agent',
      VITE_LANDING_ONLY: false,
      VITE_BASE_PATH: '/',
    });
  });

  it('requires VITE_API_URL outside development', () => {
    expect(() => parseEnv({}, false)).toThrow();
  });

  it('uses and normalises the provided values', () => {
    const env = parseEnv(
      { VITE_API_URL: 'https://api.example.com/', VITE_APP_NAME: 'Acme' },
      false,
    );
    expect(env).toMatchObject({ VITE_API_URL: 'https://api.example.com', VITE_APP_NAME: 'Acme' });
  });

  it('accepts a same-origin path and rejects other relative values', () => {
    expect(parseEnv({ VITE_API_URL: '/api/' }, false).VITE_API_URL).toBe('/api');
    expect(() => parseEnv({ VITE_API_URL: 'api' }, false)).toThrow();
    expect(() => parseEnv({ VITE_API_URL: '//evil.example.com' }, false)).toThrow();
  });

  it('does not require VITE_API_URL in landing-only mode', () => {
    const env = parseEnv({ VITE_LANDING_ONLY: 'true' }, false);
    expect(env.VITE_LANDING_ONLY).toBe(true);
  });

  it('still requires VITE_API_URL when landing-only is explicitly false', () => {
    expect(() => parseEnv({ VITE_LANDING_ONLY: 'false' }, false)).toThrow();
  });

  it('normalises the base path with leading and trailing slashes', () => {
    expect(parseEnv({ VITE_BASE_PATH: 'langgraph-brain-agent' }, true).VITE_BASE_PATH).toBe(
      '/langgraph-brain-agent/',
    );
    expect(parseEnv({ VITE_BASE_PATH: '/langgraph-brain-agent/' }, true).VITE_BASE_PATH).toBe(
      '/langgraph-brain-agent/',
    );
    expect(parseEnv({ VITE_BASE_PATH: '/' }, true).VITE_BASE_PATH).toBe('/');
  });
});
