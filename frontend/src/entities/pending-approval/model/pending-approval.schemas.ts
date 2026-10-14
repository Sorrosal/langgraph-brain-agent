import { z } from 'zod';
import { pendingInterruptSchema } from '@/shared/api/contracts';

export const pendingApprovalSchema = z.object({
  thread_id: z.string(),
  title: z.string(),
  updated_at: z.string(),
  /** When the server dismisses the request on its own; absent on older backends. */
  expires_at: z.string().nullish(),
  interrupt: pendingInterruptSchema,
});

export type PendingApproval = z.infer<typeof pendingApprovalSchema>;
