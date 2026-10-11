import { z } from 'zod';

export const checkpointSchema = z.object({
  checkpoint_id: z.string(),
  step: z.number(),
  created_at: z.string().nullable(),
  source: z.string(),
  writes: z.array(z.string()),
  next: z.array(z.string()),
  message_count: z.number(),
});

export type Checkpoint = z.infer<typeof checkpointSchema>;
