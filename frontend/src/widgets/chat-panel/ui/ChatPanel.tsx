import { useEffect, useRef } from 'react';
import { ApprovalReview } from '@/features/review-approval';
import { MessageComposer } from '@/features/send-message';
import { useThreadStream } from '@/features/thread-stream';
import { MessageBubble } from '@/entities/message';
import { useThread } from '@/entities/thread';
import type { ThreadDetail } from '@/entities/thread';
import { Skeleton } from '@/shared/ui/skeleton';
import { cn } from '@/shared/lib/cn';
import { deriveChatView } from '../lib/chat-state';

interface ChatPanelProps {
  threadId: string;
  className?: string;
}

interface ChatSessionProps {
  detail: ThreadDetail;
}

function ChatSession({ detail }: ChatSessionProps) {
  const { state, markRunStarted, markRunStartFailed } = useThreadStream(detail.id);
  const view = deriveChatView(detail, state);
  const scroller = useRef<HTMLDivElement>(null);
  const showStreaming = view.status === 'running' && state.streamingText !== '';

  useEffect(() => {
    const element = scroller.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [detail.messages.length, state.streamingText, view.pendingInterrupt]);

  return (
    <>
      <div ref={scroller} className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
        {detail.messages.length === 0 && !showStreaming && (
          <p className="text-muted-foreground m-auto text-sm">Send a message to start.</p>
        )}
        {detail.messages.map((message, index) => (
          <MessageBubble key={message.id ?? index} message={message} />
        ))}
        <div aria-live="polite" className="flex flex-col">
          {showStreaming && (
            <MessageBubble
              message={{ id: null, role: 'ai', content: state.streamingText, tool_calls: [] }}
            />
          )}
        </div>
        {view.failure && (
          <p role="alert" className="text-destructive text-sm">
            {view.failure}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-3 border-t p-3">
        <p role="status" className="text-muted-foreground min-h-5 text-xs">
          {view.activityLabel}
        </p>
        {view.pendingInterrupt && (
          <ApprovalReview
            threadId={detail.id}
            interrupt={view.pendingInterrupt}
            onSubmitting={markRunStarted}
            onSubmitFailed={markRunStartFailed}
          />
        )}
        <MessageComposer
          threadId={detail.id}
          disabled={view.busy}
          onSubmitting={markRunStarted}
          onSubmitFailed={markRunStartFailed}
        />
      </div>
    </>
  );
}

export function ChatPanel({ threadId, className }: ChatPanelProps) {
  const { data: detail, isLoading, isError } = useThread(threadId);

  return (
    <section aria-label="Conversation" className={cn('flex min-h-0 flex-col', className)}>
      {isLoading && <Skeleton className="m-4 h-24" />}
      {isError && (
        <p role="alert" className="text-destructive m-4 text-sm">
          This conversation could not be loaded.
        </p>
      )}
      {/* keyed so the stream state starts clean for every thread */}
      {detail && <ChatSession key={detail.id} detail={detail} />}
    </section>
  );
}
