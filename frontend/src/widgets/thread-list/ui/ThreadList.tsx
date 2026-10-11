import { Plus } from 'lucide-react';
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
  const navigate = useNavigate();
  const { data: threads, isLoading, isError } = useThreads();
  const { mutate: createThread, isPending } = useCreateThread();

  function startConversation() {
    createThread(undefined, {
      onSuccess: (thread) => {
        void navigate(`/app/chat/${thread.id}`);
      },
    });
  }

  return (
    <div className={cn('flex min-h-0 flex-col gap-2 p-3', className)}>
      <Button onClick={startConversation} disabled={isPending} className="w-full">
        <Plus /> New conversation
      </Button>
      <nav aria-label="Conversations" className="min-h-0 flex-1 overflow-y-auto">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {isError && <p className="text-destructive p-2 text-sm">Could not load conversations.</p>}
        {threads?.length === 0 && (
          <p className="text-muted-foreground p-2 text-sm">No conversations yet.</p>
        )}
        <ul className="flex flex-col gap-1">
          {threads?.map((thread) => (
            <li key={thread.id}>
              <NavLink
                to={`/app/chat/${thread.id}`}
                className={({ isActive }) =>
                  cn(
                    'flex flex-col rounded-md px-3 py-2 text-sm transition-colors',
                    isActive ? 'bg-accent font-medium' : 'hover:bg-accent/60',
                  )
                }
              >
                <span className="truncate">{thread.title || 'New conversation'}</span>
                <span className="text-muted-foreground text-xs">
                  {formatRelativeTime(thread.updated_at)}
                </span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
