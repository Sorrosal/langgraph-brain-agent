import { z } from 'zod';
import { i18n } from '@/shared/i18n';

// Messages resolve at validation time so they follow the active language.
export const addOrgKnowledgeSchema = z.object({
  text: z
    .string()
    .trim()
    .min(1, { error: () => i18n.t('brain:org.add.errors.required') })
    .max(2000, { error: () => i18n.t('brain:org.add.errors.tooLong') }),
});

export type AddOrgKnowledgeValues = z.infer<typeof addOrgKnowledgeSchema>;
