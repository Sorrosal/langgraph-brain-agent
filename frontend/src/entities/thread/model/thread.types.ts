import type { z } from 'zod';
import type { runStatusSchema, threadDetailSchema, threadSchema } from './thread.schemas';

export type Thread = z.infer<typeof threadSchema>;
export type ThreadDetail = z.infer<typeof threadDetailSchema>;
export type RunStatus = z.infer<typeof runStatusSchema>;
