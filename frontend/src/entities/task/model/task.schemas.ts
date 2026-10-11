import { z } from 'zod';

export const taskStatusSchema = z.enum(['open', 'done']);

export const taskSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  due_date: z.string().nullish(),
  priority: z.enum(['low', 'normal', 'high']),
  status: taskStatusSchema,
  assignee: z.string().nullish(),
  created_at: z.string(),
});

export type Task = z.infer<typeof taskSchema>;
export type TaskStatus = z.infer<typeof taskStatusSchema>;
