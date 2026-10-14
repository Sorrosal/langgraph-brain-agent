import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useCreateThread } from '@/entities/thread';
import { ChatPanel, ChatSuggestions } from '@/widgets/chat-panel';
import type { ChatLocationState } from '@/widgets/chat-panel';
import { ThreadList } from '@/widgets/thread-list';
import { cn } from '@/shared/lib/cn';

export default function ChatPage() {
  const { t } = useTranslation('chat');
  const { threadId } = useParams();
  const navigate = useNavigate();
  const { mutate: createThread, isPending } = useCreateThread();

  function startWith(prompt: string) {
    createThread(undefined, {
      onSuccess: (thread) => {
        const state: ChatLocationState = { prompt };
        void navigate(`/app/chat/${thread.id}`, { state });
      },
    });
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(0,1fr)] md:grid-cols-[17rem_minmax(0,1fr)]">
      <h1 className="sr-only">{t('title')}</h1>
      <aside
        aria-label={t('conversations')}
        className={cn('bg-subtle/60 min-h-0 border-r', threadId ? 'hidden md:flex' : 'flex')}
      >
        <ThreadList className="w-full" />
      </aside>
      <div className={cn('min-h-0 flex-col', threadId ? 'flex' : 'hidden md:flex')}>
        {threadId ? (
          <>
            <Link
              to="/app/chat"
              className="text-muted-foreground hover:text-foreground flex min-h-11 items-center gap-1.5 border-b px-4 text-sm md:hidden"
            >
              <ArrowLeft className="size-4" aria-hidden="true" /> {t('backToConversations')}
            </Link>
            <ChatPanel threadId={threadId} className="min-h-0 flex-1" />
          </>
        ) : (
          <div className="flex min-h-0 flex-1 overflow-y-auto px-4 py-10">
            <ChatSuggestions
              className="m-auto"
              title={t('welcome.title')}
              subtitle={t('welcome.subtitle')}
              onPick={startWith}
              disabled={isPending}
            />
          </div>
        )}
      </div>
    </div>
  );
}
