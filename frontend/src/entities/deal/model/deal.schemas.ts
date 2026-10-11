import { z } from 'zod';

export const dealStageSchema = z.enum(['lead', 'qualified', 'proposal', 'won', 'lost']);

export const dealSchema = z.object({
  id: z.string(),
  contact_id: z.string(),
  title: z.string(),
  // pydantic serialises Decimal as a string
  amount: z.coerce.number(),
  currency: z.string(),
  stage: dealStageSchema,
  updated_at: z.string(),
});

export type Deal = z.infer<typeof dealSchema>;
export type DealStage = z.infer<typeof dealStageSchema>;
