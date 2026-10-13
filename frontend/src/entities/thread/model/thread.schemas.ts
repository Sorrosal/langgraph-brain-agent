import { z } from 'zod';
import { messageSchema, pendingInterruptSchema } from '@/shared/api/contracts';

export const threadSchema = z.object({
  id: z.string(),
  title: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

/** What the agent's last model call was given (see the backend reason node). */
export const contextReportSchema = z.object({
  step: z.number(),
  system_tokens: z.number(),
  turn_context: z.string(),
  turn_context_tokens: z.number(),
  history_messages: z.number(),
  history_tokens: z.number(),
  cleared_tool_results: z.number(),
  untrusted_in_turn: z.boolean(),
});

export const runStatusSchema = z.enum(['idle', 'running', 'interrupted', 'failed']);

export const threadDetailSchema = threadSchema.extend({
  messages: z.array(messageSchema),
  summary: z.string().nullable(),
  pending_interrupt: pendingInterruptSchema.nullable(),
  run: z.object({ status: runStatusSchema, error: z.string().nullish() }),
  approvals: z.array(z.record(z.string(), z.unknown())),
  context_report: contextReportSchema.nullish(),
});
