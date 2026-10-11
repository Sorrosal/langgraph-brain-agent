import { z } from 'zod';
import { userSchema } from '@/entities/user';

const MIN_PASSWORD_LENGTH = 10;

export const loginSchema = z.object({
  email: z.email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

export const registerSchema = z
  .object({
    display_name: z.string().trim().min(1, 'Name is required').max(100),
    email: z.email('Please enter a valid email address'),
    password: z
      .string()
      .min(
        MIN_PASSWORD_LENGTH,
        `Password must be at least ${String(MIN_PASSWORD_LENGTH)} characters`,
      )
      .max(128),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword'],
  });

export const tokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.literal('bearer'),
  expires_in: z.number(),
  user: userSchema,
});

export const persistedSessionSchema = z.object({
  token: z.string(),
  user: userSchema,
  expiresAt: z.number(),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
export type RegisterFormValues = z.infer<typeof registerSchema>;
export type TokenResponse = z.infer<typeof tokenResponseSchema>;
