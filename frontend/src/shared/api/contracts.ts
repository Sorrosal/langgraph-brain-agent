/**
 * Wire contracts of the backend (mirrors `brain_agent.hitl.models` and the thread routes).
 * They live in shared/ so entities that compose them (thread detail = messages + interrupt)
 * do not have to import each other.
 */
import { z } from 'zod';

const argsSchema = z.record(z.string(), z.unknown());

export const toolCallSchema = z.object({
  id: z.string().nullish(),
  name: z.string(),
  args: argsSchema,
});

export const messageSchema = z.object({
  id: z.string().nullable(),
  role: z.enum(['human', 'ai', 'tool']),
  content: z.string(),
  tool_calls: z.array(toolCallSchema).default([]),
  tool_call_id: z.string().nullish(),
  status: z.string().nullish(),
});

export const riskSchema = z.enum(['low', 'medium', 'high']);

export const actionRequestSchema = z.object({
  action_id: z.string(),
  tool_name: z.string(),
  args: argsSchema,
  risk: riskSchema,
  reason: z.string(),
});

export const uncertainActionSchema = z.object({
  action_id: z.string(),
  tool_name: z.string(),
  args: argsSchema,
  message: z.string(),
});

export const approvalInterruptSchema = z.object({
  kind: z.literal('approval_required'),
  actions: z.array(actionRequestSchema),
});

export const uncertainExecutionInterruptSchema = z.object({
  kind: z.literal('uncertain_execution'),
  actions: z.array(uncertainActionSchema),
});

export const pendingInterruptSchema = z.discriminatedUnion('kind', [
  approvalInterruptSchema,
  uncertainExecutionInterruptSchema,
]);

export const approvalDecisionSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('approve') }),
  z.object({ type: z.literal('edit'), args: argsSchema }),
  z.object({ type: z.literal('reject'), reason: z.string().nullish() }),
  z.object({ type: z.literal('respond'), message: z.string() }),
]);

export const approvalResponseSchema = z.object({
  decisions: z.record(z.string(), approvalDecisionSchema),
});

export const uncertainDecisionSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('confirm_done'), message: z.string().nullish() }),
  z.object({ type: z.literal('retry') }),
  z.object({ type: z.literal('skip') }),
]);

export const uncertainResponseSchema = z.object({
  decisions: z.record(z.string(), uncertainDecisionSchema),
});
