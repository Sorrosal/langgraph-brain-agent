import { z } from 'zod';
import { messageSchema, pendingInterruptSchema } from '@/shared/api/contracts';

export const threadSchema = z.object({
  id: z.string(),
  title: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const runStatusSchema = z.enum(['idle', 'running', 'interrupted', 'failed']);

export const threadDetailSchema = threadSchema.extend({
  messages: z.array(messageSchema),
  summary: z.string().nullable(),
  pending_interrupt: pendingInterruptSchema.nullable(),
  run: z.object({ status: runStatusSchema, error: z.string().nullish() }),
  approvals: z.array(z.record(z.string(), z.unknown())),
});
