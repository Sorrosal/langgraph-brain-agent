import type { z } from 'zod';
import type { messageSchema, toolCallSchema } from '@/shared/api/contracts';

export type Message = z.infer<typeof messageSchema>;
export type ToolCall = z.infer<typeof toolCallSchema>;
