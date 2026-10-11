import type { RunStatus, ThreadDetail } from '@/entities/thread';
import type { StreamState } from '@/features/thread-stream';

export interface ChatView {
  status: RunStatus;
  pendingInterrupt: ThreadDetail['pending_interrupt'];
  failure: string | null;
  /** What the assistant is doing right now, when it is doing something. */
  activityLabel: string | null;
  /** The composer is locked: a run is active or waiting for a decision. */
  busy: boolean;
}

/** The live stream wins once it has spoken; until then the persisted thread detail decides. */
export function deriveChatView(detail: ThreadDetail, stream: StreamState): ChatView {
  const status = stream.runStatus ?? detail.run.status;
  const runningTool = stream.toolActivity.find((tool) => tool.status === 'running');
  const activityLabel =
    status === 'interrupted'
      ? 'Waiting for your approval'
      : status === 'running'
        ? runningTool
          ? `Running tool ${runningTool.name}…`
          : 'Thinking…'
        : null;
  return {
    status,
    pendingInterrupt:
      status === 'interrupted' ? (stream.pendingInterrupt ?? detail.pending_interrupt) : null,
    failure:
      status === 'failed'
        ? (stream.error?.message ?? 'The run failed. Send a message to retry.')
        : null,
    activityLabel,
    busy: status === 'running' || status === 'interrupted',
  };
}
