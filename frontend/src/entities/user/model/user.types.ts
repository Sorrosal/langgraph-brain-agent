import type { z } from 'zod';
import type { userRoleSchema, userSchema } from './user.schemas';

export type User = z.infer<typeof userSchema>;
export type UserRole = z.infer<typeof userRoleSchema>;
