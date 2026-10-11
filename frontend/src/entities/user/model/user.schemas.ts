import { z } from 'zod';

export const userRoleSchema = z.enum(['admin', 'operator']);

export const userSchema = z.object({
  id: z.string(),
  email: z.string(),
  display_name: z.string(),
  role: userRoleSchema,
  created_at: z.string(),
});
