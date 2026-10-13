import { z } from 'zod';
import { userSchema } from '@/entities/user';

export const MIN_PASSWORD_LENGTH = 10;
const MAX_PASSWORD_LENGTH = 128;
const MAX_NAME_LENGTH = 100;

/**
 * Interpolation values for the validation messages. The schemas carry translation keys, not
 * text, so the message follows the language active when the error is shown, not when it was raised.
 */
export const VALIDATION_LIMITS = {
  min: MIN_PASSWORD_LENGTH,
  passwordMax: MAX_PASSWORD_LENGTH,
  nameMax: MAX_NAME_LENGTH,
};

export const loginSchema = z.object({
  email: z.email('auth:validation.email'),
  password: z.string().min(1, 'auth:validation.passwordRequired'),
});

export const registerSchema = z
  .object({
    display_name: z
      .string()
      .trim()
      .min(1, 'auth:validation.nameRequired')
      .max(MAX_NAME_LENGTH, 'auth:validation.nameMax'),
    email: z.email('auth:validation.email'),
    password: z
      .string()
      .min(MIN_PASSWORD_LENGTH, 'auth:validation.passwordMin')
      .max(MAX_PASSWORD_LENGTH, 'auth:validation.passwordMax'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'auth:validation.passwordMismatch',
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
