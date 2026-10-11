import { z } from 'zod';
import { riskSchema } from '@/shared/api/contracts';

export const guidelineSchema = z.object({
  id: z.string(),
  text: z.string(),
  priority: z.number().default(0),
});

export const hardRuleSchema = z.object({
  id: z.string(),
  description: z.string(),
  when: z.object({ tool: z.string() }).loose(),
  action: z.enum(['require_approval', 'block']),
  risk: riskSchema.default('high'),
  reason: z.string().nullish(),
});

export const rulesSchema = z.object({
  version_hash: z.string(),
  persona: z.string().nullable(),
  guidelines: z.array(guidelineSchema),
  hard_rules: z.array(hardRuleSchema),
  files: z.array(z.object({ name: z.string(), content: z.string() })),
});

export const ruleSavedSchema = z.object({ filename: z.string(), version_hash: z.string() });

export type Guideline = z.infer<typeof guidelineSchema>;
export type HardRule = z.infer<typeof hardRuleSchema>;
export type Rules = z.infer<typeof rulesSchema>;
