import { z } from 'zod';

const DEV_API_URL = 'http://localhost:8000';

const envSchema = z.object({
  // Absolute URL, or a same-origin path such as `/api` (behind a reverse proxy).
  VITE_API_URL: z
    .union([z.url(), z.string().regex(/^\/(?!\/)/)])
    .transform((url) => url.replace(/\/+$/, '')),
  VITE_APP_NAME: z.string().default('Brain Agent'),
  VITE_LANDING_ONLY: z
    .enum(['true', 'false'])
    .default('false')
    .transform((value) => value === 'true'),
  VITE_BASE_PATH: z
    .string()
    .default('/')
    .transform((path) => `/${path.replace(/^\/+|\/+$/g, '')}/`.replace(/^\/\/$/, '/')),
});

export type Env = z.infer<typeof envSchema>;

/**
 * `VITE_API_URL` defaults to the local backend in development only; app builds must set it.
 * A landing-only build never calls the API, so it falls back to the dev URL as an unused placeholder.
 */
export function parseEnv(raw: Record<string, unknown>, isDev: boolean): Env {
  const landingOnly = raw['VITE_LANDING_ONLY'] === 'true';
  return envSchema.parse({
    ...raw,
    VITE_API_URL: raw['VITE_API_URL'] ?? (isDev || landingOnly ? DEV_API_URL : undefined),
  });
}

export const env = parseEnv(import.meta.env, import.meta.env.DEV);
