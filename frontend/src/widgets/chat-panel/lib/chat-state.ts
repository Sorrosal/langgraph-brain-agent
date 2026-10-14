import type { RunStatus, ThreadDetail } from '@/entities/thread';
import type { StreamState } from '@/features/thread-stream';

/** `run_failed` code the backend sends when the user stopped the run. */
export const RUN_CANCELLED = 'run_cancelled';

export type ChatActivity =
  | { kind: 'thinking' }
  | { kind: 'tool'; name: string }
  | { kind: 'approval' };

export interface ChatView {
  status: RunStatus;
  pendingInterrupt: ThreadDetail['pending_interrupt'];
  /** The stream's error message, or `true` for a failure without one (show the generic text).
   *  Null when the run did not fail or was stopped on purpose (see `cancelled`). */
  failure: string | true | null;
  /** The user stopped the run: a neutral notice, not an error. */
  cancelled: boolean;
  /** What the assistant is doing right now, when it is doing something. */
  activity: ChatActivity | null;
  /** The composer is locked: a run is active or waiting for a decision. */
  busy: boolean;
}

/** The live stream wins once it has spoken; until then the persisted thread detail decides. */
export function deriveChatView(detail: ThreadDetail, stream: StreamState): ChatView {
  const status = stream.runStatus ?? detail.run.status;
  const runningTool = stream.toolActivity.find((tool) => tool.status === 'running');
  const activity: ChatActivity | null =
    status === 'interrupted'
      ? { kind: 'approval' }
      : status === 'running'
        ? runningTool
          ? { kind: 'tool', name: runningTool.name }
          : { kind: 'thinking' }
        : null;
  // The live stream knows why the run ended; after a reload the persisted run says so.
  const cancelled =
    status === 'failed' &&
    (stream.error?.code ?? (stream.runStatus === null ? detail.run.code : null)) === RUN_CANCELLED;
  return {
    status,
    pendingInterrupt:
      status === 'interrupted' ? (stream.pendingInterrupt ?? detail.pending_interrupt) : null,
    failure: status === 'failed' && !cancelled ? (stream.error?.message ?? true) : null,
    cancelled,
    activity,
    busy: status === 'running' || status === 'interrupted',
  };
}
