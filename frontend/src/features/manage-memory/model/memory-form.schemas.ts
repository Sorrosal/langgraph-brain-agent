import { z } from 'zod';
import { memoryKindSchema } from '@/entities/memory';

export const addMemorySchema = z.object({
  kind: memoryKindSchema,
  text: z.string().trim().min(1, 'Enter some text').max(2000, 'At most 2000 characters'),
});

export type AddMemoryValues = z.infer<typeof addMemorySchema>;
