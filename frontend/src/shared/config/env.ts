import { z } from 'zod';

const envSchema = z.object({
  VITE_API_URL: z.url(),
  VITE_APP_NAME: z.string().default('React Spark'),
});

// Zod v4 parse returns the validated object
export const env = envSchema.parse(import.meta.env);
