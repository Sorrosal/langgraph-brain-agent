import { z } from 'zod';

export const memoryKindSchema = z.enum(['fact', 'preference', 'episode']);

export const memorySchema = z.object({
  id: z.string(),
  kind: memoryKindSchema,
  text: z.string(),
  source_thread_id: z.string().nullable(),
  created_at: z.string(),
  score: z.number().nullable(),
});

export type Memory = z.infer<typeof memorySchema>;
export type MemoryKind = z.infer<typeof memoryKindSchema>;
