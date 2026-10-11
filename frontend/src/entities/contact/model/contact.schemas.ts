import { z } from 'zod';

export const contactSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string(),
  company: z.string(),
  phone: z.string().nullish(),
  tags: z.array(z.string()),
  created_at: z.string(),
});

export type Contact = z.infer<typeof contactSchema>;
