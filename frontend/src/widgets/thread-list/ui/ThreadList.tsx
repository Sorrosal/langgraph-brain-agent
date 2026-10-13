import { MessageSquarePlus, MessagesSquare } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { NavLink, useNavigate } from 'react-router-dom';
import { useCreateThread, useThreads } from '@/entities/thread';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/skeleton';
import { cn } from '@/shared/lib/cn';
import { formatRelativeTime } from '@/shared/lib/format';

interface ThreadListProps {
  className?: string;
}

export function ThreadList({ className }: ThreadListProps) {
  const { t } = useTranslation('chat');
  const navigate = useNavigate();
  const { data: threads, isLoading, isError, refetch } = useThreads();
  const { mutate: createThread, isPending } = useCreateThread();

  function startConversation() {
    createThread(undefined, {
      onSuccess: (thread) => {
        void navigate(`/app/chat/${thread.id}`);
      },
    });
  }

  return (
    <div className={cn('flex min-h-0 flex-col', className)}>
      <div className="flex items-center justify-between gap-2 px-4 pt-4 pb-3">
        <h2 className="text-sm font-semibold">{t('conversations')}</h2>
        <Button size="sm" onClick={startConversation} disabled={isPending}>
          <MessageSquarePlus /> {t('newConversation')}
        </Button>
      </div>
      <nav aria-label={t('conversations')} className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {isLoading && (
          <div className="flex flex-col gap-1.5 px-1">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        )}
        {isError && (
          <div className="flex flex-col items-start gap-2 p-2">
            <p className="text-danger-fg text-sm">{t('loadConversationsFailed')}</p>
            <Button variant="outline" size="sm" onClick={() => void refetch()}>
              {t('common:actions.retry')}
            </Button>
          </div>
        )}
        {threads?.length === 0 && (
          <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
            <MessagesSquare className="text-faint size-6" aria-hidden="true" />
            <p className="text-sm font-medium">{t('noConversations')}</p>
            <p className="text-muted-foreground text-xs">{t('noConversationsHint')}</p>
          </div>
        )}
        <ul className="flex flex-col gap-0.5">
          {threads?.map((thread) => (
            <li key={thread.id}>
              <NavLink
                to={`/app/chat/${thread.id}`}
                className={({ isActive }) =>
                  cn(
                    'flex min-h-11 flex-col justify-center rounded-[var(--radius-md)] px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-accent text-accent-foreground font-medium'
                      : 'hover:bg-muted text-foreground',
                  )
                }
              >
                <span className="truncate">{thread.title || t('untitled')}</span>
                <span className="text-faint text-2xs">{formatRelativeTime(thread.updated_at)}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
