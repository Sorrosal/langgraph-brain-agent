import { describe, expect, it } from 'vitest';
import { parseEnv } from '../env';

describe('parseEnv', () => {
  it('applies the defaults in development', () => {
    expect(parseEnv({}, true)).toEqual({
      VITE_API_URL: 'http://localhost:8000',
      VITE_APP_NAME: 'Brain Agent',
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
    expect(env).toEqual({ VITE_API_URL: 'https://api.example.com', VITE_APP_NAME: 'Acme' });
  });
});
