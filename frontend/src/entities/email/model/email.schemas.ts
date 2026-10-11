import { z } from 'zod';

export const emailFolderSchema = z.enum(['inbox', 'sent']);

export const emailSchema = z.object({
  id: z.string(),
  message_id_header: z.string(),
  from_: z.string(),
  to: z.array(z.string()),
  cc: z.array(z.string()),
  subject: z.string(),
  body_text: z.string(),
  received_at: z.string().nullish(),
  sent_at: z.string().nullish(),
  folder: emailFolderSchema,
});

export type Email = z.infer<typeof emailSchema>;
export type EmailFolder = z.infer<typeof emailFolderSchema>;
