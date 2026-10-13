import { z } from 'zod';
import { memoryKindSchema } from '@/entities/memory';
import { i18n } from '@/shared/i18n';

// Messages resolve at validation time so they follow the active language.
export const addMemorySchema = z.object({
  kind: memoryKindSchema,
  text: z
    .string()
    .trim()
    .min(1, { error: () => i18n.t('brain:memories.add.errors.required') })
    .max(2000, { error: () => i18n.t('brain:memories.add.errors.tooLong') }),
});

export type AddMemoryValues = z.infer<typeof addMemorySchema>;
