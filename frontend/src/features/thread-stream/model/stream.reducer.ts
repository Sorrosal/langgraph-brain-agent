import { z } from 'zod';
import { pendingInterruptSchema } from '@/shared/api/contracts';
import type { RunStatus } from '@/entities/thread';

type PendingInterrupt = z.infer<typeof pendingInterruptSchema>;

const streamEventSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('token'), data: z.object({ text: z.string() }) }),
  z.object({ type: z.literal('node'), data: z.object({ node: z.string() }) }),
  z.object({
    type: z.literal('tool_call'),
    data: z.object({ id: z.string(), name: z.string(), args: z.record(z.string(), z.unknown()) }),
  }),
  z.object({
    type: z.literal('tool_result'),
    data: z.object({
      id: z.string(),
      name: z.string().nullish(),
      status: z.string(),
      content: z.string(),
    }),
  }),
  z.object({ type: z.literal('interrupt'), data: pendingInterruptSchema }),
  z.object({ type: z.literal('run_completed'), data: z.object({ status: z.string() }) }),
  z.object({
    type: z.literal('run_failed'),
    data: z.object({ code: z.string(), message: z.string() }),
  }),
]);

export type StreamEvent = z.infer<typeof streamEventSchema> & { id: number };
export type StreamEventType = StreamEvent['type'];

export const STREAM_EVENT_TYPES: readonly StreamEventType[] = streamEventSchema.options.map(
  (option) => option.shape.type.value,
);

/** Validate one SSE frame; unknown or malformed events are dropped (returns null). */
export function parseStreamEvent(id: number, type: string, data: unknown): StreamEvent | null {
  const parsed = streamEventSchema.safeParse({ type, data });
  return parsed.success ? { ...parsed.data, id } : null;
}

export interface ToolActivity {
  id: string;
  name: string;
  args?: Record<string, unknown>;
  status: 'running' | 'success' | 'error';
  content?: string;
}

export interface StreamState {
  /** Highest event id applied; replayed events at or below it are ignored. */
  lastEventId: number;
  /** null until the stream has said something: the thread detail is authoritative then. */
  runStatus: RunStatus | null;
  streamingText: string;
  /** The reason node finished: the next token starts a new text segment. */
  textSealed: boolean;
  /** Last node that finished. */
  activeNode: string | null;
  toolActivity: ToolActivity[];
  pendingInterrupt: PendingInterrupt | null;
  error: { code: string; message: string } | null;
}

export type StreamAction =
  | { type: 'event'; event: StreamEvent }
  | { type: 'run_started' }
  | { type: 'reset' };

export const initialStreamState: StreamState = {
  lastEventId: 0,
  runStatus: null,
  streamingText: '',
  textSealed: false,
  activeNode: null,
  toolActivity: [],
  pendingInterrupt: null,
  error: null,
};

const REASON_NODE = 'reason';

function applyEvent(state: StreamState, event: StreamEvent): StreamState {
  switch (event.type) {
    case 'token':
      return {
        ...state,
        runStatus: 'running',
        error: null,
        streamingText: (state.textSealed ? '' : state.streamingText) + event.data.text,
        textSealed: false,
      };
    case 'node':
      return {
        ...state,
        runStatus: 'running',
        activeNode: event.data.node,
        textSealed: state.textSealed || event.data.node === REASON_NODE,
      };
    case 'tool_call': {
      const { id, name, args } = event.data;
      const known = state.toolActivity.some((tool) => tool.id === id);
      return {
        ...state,
        runStatus: 'running',
        toolActivity: known
          ? state.toolActivity
          : [...state.toolActivity, { id, name, args, status: 'running' }],
      };
    }
    case 'tool_result': {
      const { id, name, status, content } = event.data;
      const outcome = status === 'error' ? 'error' : 'success';
      const known = state.toolActivity.some((tool) => tool.id === id);
      return {
        ...state,
        toolActivity: known
          ? state.toolActivity.map((tool) =>
              tool.id === id ? { ...tool, status: outcome, content } : tool,
            )
          : [...state.toolActivity, { id, name: name ?? 'tool', status: outcome, content }],
      };
    }
    case 'interrupt':
      return { ...state, runStatus: 'interrupted', pendingInterrupt: event.data };
    case 'run_completed':
      return event.data.status === 'interrupted'
        ? { ...state, runStatus: 'interrupted' }
        : { ...initialStreamState, lastEventId: state.lastEventId, runStatus: 'idle' };
    case 'run_failed':
      return {
        ...initialStreamState,
        lastEventId: state.lastEventId,
        runStatus: 'failed',
        error: event.data,
      };
  }
}

export function streamReducer(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case 'event':
      if (action.event.id <= state.lastEventId) return state;
      return { ...applyEvent(state, action.event), lastEventId: action.event.id };
    case 'run_started':
      return { ...initialStreamState, lastEventId: state.lastEventId, runStatus: 'running' };
    case 'reset':
      return initialStreamState;
  }
}
