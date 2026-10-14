import {
  Ellipsis,
  MessagesSquare,
  MessageSquarePlus,
  Pencil,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, useMatch, useNavigate } from 'react-router-dom';
import { useCreateThread, useThreads } from '@/entities/thread';
import type { Thread } from '@/entities/thread';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
import { Input } from '@/shared/ui/input';
import { Skeleton } from '@/shared/ui/skeleton';
import { cn } from '@/shared/lib/cn';
import { formatRelativeTime } from '@/shared/lib/format';
import { DeleteThreadDialog } from './DeleteThreadDialog';
import { RenameThreadDialog } from './RenameThreadDialog';

interface ThreadListProps {
  className?: string;
}

type Pending = { kind: 'rename' | 'delete'; thread: Thread } | null;

/** Lower-case without accents, so "reunion" finds "Reunión". */
function fold(text: string): string {
  return text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
}

interface ThreadItemProps {
  thread: Thread;
  onRename: () => void;
  onDelete: () => void;
}

function ThreadItem({ thread, onRename, onDelete }: ThreadItemProps) {
  const { t } = useTranslation('chat');
  const label = thread.title || t('untitled');

  return (
    <li className="group relative">
      <NavLink
        to={`/app/chat/${thread.id}`}
        className={({ isActive }) =>
          cn(
            'flex min-h-11 flex-col justify-center rounded-[var(--radius-md)] py-2 pr-11 pl-3 text-sm transition-colors md:pr-10',
            isActive
              ? 'bg-accent text-accent-foreground font-medium'
              : 'hover:bg-muted text-foreground',
          )
        }
      >
        <span className="truncate">{label}</span>
        <span className="text-faint text-2xs">{formatRelativeTime(thread.updated_at)}</span>
      </NavLink>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t('threadMenu', { title: label })}
            className="can-hover:opacity-0 can-hover:group-hover:opacity-100 can-hover:group-focus-within:opacity-100 can-hover:data-[state=open]:opacity-100 absolute top-1/2 right-0.5 size-11 -translate-y-1/2 md:size-8"
          >
            <Ellipsis />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-40">
          <DropdownMenuItem className="max-md:min-h-11" onSelect={onRename}>
            <Pencil aria-hidden="true" />
            {t('rename.action')}
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-danger-fg focus:bg-danger-bg focus:text-danger-fg max-md:min-h-11"
            onSelect={onDelete}
          >
            <Trash2 aria-hidden="true" />
            {t('delete.action')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  );
}

export function ThreadList({ className }: ThreadListProps) {
  const { t } = useTranslation('chat');
  const navigate = useNavigate();
  const openId = useMatch('/app/chat/:threadId')?.params.threadId;
  const { data: threads, isLoading, isError, refetch } = useThreads();
  const { mutate: createThread, isPending } = useCreateThread();
  const [query, setQuery] = useState('');
  const [pending, setPending] = useState<Pending>(null);

  const needle = fold(query.trim());
  const visible = needle
    ? threads?.filter((thread) => fold(thread.title || t('untitled')).includes(needle))
    : threads;

  function startConversation() {
    createThread(undefined, {
      onSuccess: (thread) => {
        void navigate(`/app/chat/${thread.id}`);
      },
    });
  }

  function close() {
    setPending(null);
  }

  return (
    <div className={cn('flex min-h-0 flex-col', className)}>
      <div className="flex items-center justify-between gap-2 px-4 pt-4 pb-3">
        <h2 className="text-sm font-semibold">{t('conversations')}</h2>
        <Button size="sm" onClick={startConversation} disabled={isPending}>
          <MessageSquarePlus /> {t('newConversation')}
        </Button>
      </div>
      {threads && threads.length > 0 && (
        <div className="px-3 pb-2">
          <div className="relative">
            <Search
              className="text-faint pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
              aria-hidden="true"
            />
            <Input
              type="search"
              value={query}
              aria-label={t('search.label')}
              placeholder={t('search.placeholder')}
              className="pr-10 pl-9 max-md:h-11 [&::-webkit-search-cancel-button]:hidden"
              onChange={(event) => {
                setQuery(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Escape' && query) {
                  event.preventDefault();
                  setQuery('');
                }
              }}
            />
            {query && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={t('search.clear')}
                className="absolute top-1/2 right-0.5 size-9 -translate-y-1/2 max-md:size-11"
                onClick={() => {
                  setQuery('');
                }}
              >
                <X />
              </Button>
            )}
          </div>
        </div>
      )}
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
        {visible?.length === 0 && threads && threads.length > 0 && (
          <p role="status" className="text-muted-foreground px-4 py-8 text-center text-sm">
            {t('search.noResults', { query: query.trim() })}
          </p>
        )}
        <ul className="flex flex-col gap-0.5">
          {visible?.map((thread) => (
            <ThreadItem
              key={thread.id}
              thread={thread}
              onRename={() => {
                setPending({ kind: 'rename', thread });
              }}
              onDelete={() => {
                setPending({ kind: 'delete', thread });
              }}
            />
          ))}
        </ul>
      </nav>
      {pending?.kind === 'rename' && (
        <RenameThreadDialog key={pending.thread.id} thread={pending.thread} onClose={close} />
      )}
      {pending?.kind === 'delete' && (
        <DeleteThreadDialog
          key={pending.thread.id}
          thread={pending.thread}
          onClose={close}
          onDeleted={(id) => {
            if (id === openId) void navigate('/app/chat');
          }}
        />
      )}
    </div>
  );
}
