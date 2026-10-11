import { z } from 'zod';
import { pendingInterruptSchema } from '@/shared/api/contracts';

export const pendingApprovalSchema = z.object({
  thread_id: z.string(),
  title: z.string(),
  updated_at: z.string(),
  interrupt: pendingInterruptSchema,
});

export type PendingApproval = z.infer<typeof pendingApprovalSchema>;
