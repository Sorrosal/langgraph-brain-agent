import { ArrowDown, CircleAlert, CircleCheck, LoaderCircle, Square, Wrench } from 'lucide-react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { notifyRunFailed } from '@/features/notifications';
import { ApprovalReview } from '@/features/review-approval';
import { MessageComposer, useSendMessage } from '@/features/send-message';
import { useThreadStream } from '@/features/thread-stream';
import type { ToolActivity } from '@/features/thread-stream';
import { AssistantMark, AssistantText, MessageBubble } from '@/entities/message';
import { useCancelRun, useThread } from '@/entities/thread';
import type { ThreadDetail } from '@/entities/thread';
import { ApiError } from '@/shared/api/api-error';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/skeleton';
import { cn } from '@/shared/lib/cn';
import { deriveChatView, RUN_CANCELLED } from '../lib/chat-state';
import type { ChatActivity } from '../lib/chat-state';
import { ChatSuggestions } from './ChatSuggestions';

/** Distance from the bottom (px) under which the thread keeps following new content. */
const STICKY_THRESHOLD = 96;

interface ChatPanelProps {
  threadId: string;
  className?: string;
}

/** Router state that carries a first message into a freshly created thread. */
export interface ChatLocationState {
  prompt?: string;
}

function LiveTool({ tool }: { tool: ToolActivity }) {
  const { t } = useTranslation('chat');
  const label = t(`common:tools.${tool.name}`, { defaultValue: tool.name });
  const Icon =
    tool.status === 'running' ? LoaderCircle : tool.status === 'error' ? CircleAlert : CircleCheck;
  return (
    <li className="bg-subtle inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1 text-xs">
      <Wrench className="text-brand-ink size-3.5" aria-hidden="true" />
      <span className="font-medium">{label}</span>
      <Icon
        aria-label={t(
          tool.status === 'running'
            ? 'tool.running'
            : tool.status === 'error'
              ? 'tool.failed'
              : 'tool.done',
        )}
        className={cn(
          'size-3.5',
          tool.status === 'running' && 'text-muted-foreground animate-spin',
          tool.status === 'error' && 'text-danger',
          tool.status === 'success' && 'text-success',
        )}
      />
    </li>
  );
}

function activityText(activity: ChatActivity, t: TFunction<'chat'>) {
  if (activity.kind === 'approval') return t('activity.waitingApproval');
  if (activity.kind === 'tool') {
    return t('activity.runningTool', {
      tool: t(`common:tools.${activity.name}`, { defaultValue: activity.name }),
    });
  }
  return t('activity.thinking');
}

interface ChatSessionProps {
  detail: ThreadDetail;
  initialPrompt: string | undefined;
  onInitialPromptUsed: () => void;
}

function ChatSession({ detail, initialPrompt, onInitialPromptUsed }: ChatSessionProps) {
  const { t } = useTranslation('chat');
  const { state, markRunStarted, markRunStartFailed, settle } = useThreadStream(detail.id);
  const { mutate: sendMessage, isPending: sending } = useSendMessage(detail.id);
  const { mutate: cancelRun, isPending: stopping } = useCancelRun(detail.id);
  const view = deriveChatView(detail, state);
  const scroller = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const [showJump, setShowJump] = useState(false);
  /** The message just sent, shown until the persisted thread contains it. */
  const [pending, setPending] = useState<{ text: string; base: number } | null>(null);

  const showPending = pending !== null && detail.messages.length <= pending.base;
  const live = view.status === 'running' || state.settled;
  const liveTools = live ? state.toolActivity : [];
  const liveText = live ? state.streamingText : '';
  const thinking = view.status === 'running' && liveText === '';

  // A refetched detail after the run finished replaces the streamed preview.
  useEffect(() => {
    settle();
  }, [detail, settle]);

  // One bell entry per failed run; a deliberate stop is not a failure.
  useEffect(() => {
    if (state.error && state.error.code !== RUN_CANCELLED) notifyRunFailed(detail);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per `run_failed` event
  }, [state.error]);

  function stop() {
    cancelRun(undefined, {
      onError: (error) => {
        // 409 `not_running`: it finished on its own, the refetched detail says so.
        if (!ApiError.isApiError(error) || error.status !== 409) toast.error(t('stopFailed'));
      },
    });
  }

  function send(text: string, onSent: () => void = () => undefined) {
    following.current = true;
    markRunStarted();
    setPending({ text, base: detail.messages.length });
    sendMessage(text, {
      onSuccess: onSent,
      onError: () => {
        markRunStartFailed();
        setPending(null);
      },
    });
  }

  // A suggestion picked before the thread existed is sent once the thread is open. Deferred
  // and cancellable: StrictMode's mount/unmount/mount would otherwise orphan the mutation's
  // observer and leave `sending` stuck at true.
  useEffect(() => {
    if (!initialPrompt) return;
    const timer = setTimeout(() => {
      onInitialPromptUsed();
      if (detail.messages.length === 0 && !view.busy) send(initialPrompt);
    }, 0);
    return () => {
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per opened thread
  }, []);

  // Follow new content only while the reader is at the bottom; never yank them back up.
  useLayoutEffect(() => {
    const element = scroller.current;
    if (element && following.current) element.scrollTop = element.scrollHeight;
  }, [
    detail.messages.length,
    liveText,
    liveTools.length,
    showPending,
    view.pendingInterrupt,
    thinking,
  ]);

  function onScroll() {
    const element = scroller.current;
    if (!element) return;
    const atBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight < STICKY_THRESHOLD;
    following.current = atBottom;
    setShowJump(!atBottom);
  }

  function jumpToLatest() {
    const element = scroller.current;
    if (!element) return;
    following.current = true;
    element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
  }

  const empty = detail.messages.length === 0 && !showPending && !live;

  return (
    <>
      <div className="relative flex min-h-0 flex-1 flex-col">
        <div
          ref={scroller}
          onScroll={onScroll}
          className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto"
        >
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6 sm:px-6">
            {empty && (
              <ChatSuggestions
                className="my-auto pt-[8vh]"
                title={t('welcome.emptyThread')}
                onPick={(prompt) => {
                  send(prompt);
                }}
                disabled={view.busy || sending}
              />
            )}
            {detail.messages.map((message, index) => (
              <MessageBubble key={message.id ?? index} message={message} />
            ))}
            {showPending && (
              <MessageBubble
                className="opacity-80"
                message={{ id: null, role: 'human', content: pending.text, tool_calls: [] }}
              />
            )}
            {(liveTools.length > 0 || liveText || thinking) && (
              <div
                data-message
                className="flex max-w-full min-w-0 gap-3 self-start"
                aria-live="polite"
              >
                <AssistantMark className={cn('mt-0.5', thinking && 'animate-pulse')} />
                <div className="flex min-w-0 flex-col gap-2 pt-0.5">
                  {liveTools.length > 0 && (
                    <ul className="flex flex-col gap-1.5">
                      {liveTools.map((tool) => (
                        <LiveTool key={tool.id} tool={tool} />
                      ))}
                    </ul>
                  )}
                  {liveText ? (
                    <AssistantText text={liveText} />
                  ) : (
                    thinking && (
                      <span className="ev-typing" aria-hidden="true">
                        <span />
                        <span />
                        <span />
                      </span>
                    )
                  )}
                </div>
              </div>
            )}
            {view.failure !== null && (
              <p
                role="alert"
                className="border-danger-border bg-danger-bg text-danger-fg flex items-start gap-2 rounded-[var(--radius-md)] border px-3 py-2 text-sm"
              >
                <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                {view.failure === true ? t('failure') : view.failure}
              </p>
            )}
            {view.cancelled && (
              <p
                role="status"
                className="bg-subtle text-muted-foreground flex items-start gap-2 rounded-[var(--radius-md)] border px-3 py-2 text-sm"
              >
                <Square className="mt-1 size-3 shrink-0 fill-current" aria-hidden="true" />
                {t('stopped')}
              </p>
            )}
          </div>
        </div>
        {showJump && (
          <Button
            variant="outline"
            size="sm"
            onClick={jumpToLatest}
            className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full"
          >
            <ArrowDown /> {t('jumpToLatest')}
          </Button>
        )}
      </div>

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-3 px-4 pt-1 pb-4 sm:px-6">
        <p role="status" className="sr-only">
          {view.activity ? activityText(view.activity, t) : ''}
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
          busy={view.busy}
          waitingApproval={view.status === 'interrupted'}
          sending={sending}
          onSend={send}
          onStop={stop}
          stopping={stopping}
        />
      </div>
    </>
  );
}

export function ChatPanel({ threadId, className }: ChatPanelProps) {
  const { t } = useTranslation('chat');
  const { data: detail, isLoading, isError, refetch } = useThread(threadId);
  const location = useLocation();
  const navigate = useNavigate();
  const initialPrompt = (location.state as ChatLocationState | null)?.prompt;

  return (
    <section aria-label={t('conversation')} className={cn('flex min-h-0 flex-col', className)}>
      {isLoading && (
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-6 py-6">
          <Skeleton className="h-10 w-2/5 self-end rounded-[var(--radius-xl)]" />
          <Skeleton className="h-20 w-4/5" />
          <Skeleton className="h-10 w-1/3 self-end rounded-[var(--radius-xl)]" />
        </div>
      )}
      {isError && (
        <div role="alert" className="m-auto flex flex-col items-center gap-3 p-6 text-center">
          <p className="text-muted-foreground text-sm">{t('loadConversationFailed')}</p>
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            {t('common:actions.retry')}
          </Button>
        </div>
      )}
      {/* keyed so the stream state starts clean for every thread */}
      {detail && (
        <ChatSession
          key={detail.id}
          detail={detail}
          initialPrompt={initialPrompt}
          onInitialPromptUsed={() => {
            void navigate(location.pathname, { replace: true, state: null });
          }}
        />
      )}
    </section>
  );
}
