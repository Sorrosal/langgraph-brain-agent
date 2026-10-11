import type { z } from 'zod';
import type {
  actionRequestSchema,
  approvalDecisionSchema,
  approvalInterruptSchema,
  approvalResponseSchema,
  pendingInterruptSchema,
  uncertainActionSchema,
  uncertainDecisionSchema,
  uncertainExecutionInterruptSchema,
  uncertainResponseSchema,
} from '@/shared/api/contracts';

export type ActionRequest = z.infer<typeof actionRequestSchema>;
export type UncertainAction = z.infer<typeof uncertainActionSchema>;
export type ApprovalInterrupt = z.infer<typeof approvalInterruptSchema>;
export type UncertainExecutionInterrupt = z.infer<typeof uncertainExecutionInterruptSchema>;
export type PendingInterrupt = z.infer<typeof pendingInterruptSchema>;
export type ApprovalDecision = z.infer<typeof approvalDecisionSchema>;
export type ApprovalResponse = z.infer<typeof approvalResponseSchema>;
export type UncertainDecision = z.infer<typeof uncertainDecisionSchema>;
export type UncertainResponse = z.infer<typeof uncertainResponseSchema>;
