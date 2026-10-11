import { z } from 'zod';

const DEV_API_URL = 'http://localhost:8000';

const envSchema = z.object({
  VITE_API_URL: z.url().transform((url) => url.replace(/\/+$/, '')),
  VITE_APP_NAME: z.string().default('Brain Agent'),
});

export type Env = z.infer<typeof envSchema>;

/** `VITE_API_URL` defaults to the local backend in development only; builds must set it. */
export function parseEnv(raw: Record<string, unknown>, isDev: boolean): Env {
  return envSchema.parse({
    ...raw,
    VITE_API_URL: raw['VITE_API_URL'] ?? (isDev ? DEV_API_URL : undefined),
  });
}

export const env = parseEnv(import.meta.env, import.meta.env.DEV);
