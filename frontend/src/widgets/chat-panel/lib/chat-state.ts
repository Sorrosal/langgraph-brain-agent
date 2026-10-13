import type { RunStatus, ThreadDetail } from '@/entities/thread';
import type { StreamState } from '@/features/thread-stream';

export type ChatActivity =
  | { kind: 'thinking' }
  | { kind: 'tool'; name: string }
  | { kind: 'approval' };

export interface ChatView {
  status: RunStatus;
  pendingInterrupt: ThreadDetail['pending_interrupt'];
  /** The stream's error message, or `true` for a failure without one (show the generic text). */
  failure: string | true | null;
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
  return {
    status,
    pendingInterrupt:
      status === 'interrupted' ? (stream.pendingInterrupt ?? detail.pending_interrupt) : null,
    failure: status === 'failed' ? (stream.error?.message ?? true) : null,
    activity,
    busy: status === 'running' || status === 'interrupted',
  };
}
