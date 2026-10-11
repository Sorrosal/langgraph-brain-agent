import { ArrowLeft } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { ChatPanel } from '@/widgets/chat-panel';
import { ThreadList } from '@/widgets/thread-list';
import { cn } from '@/shared/lib/cn';

export default function ChatPage() {
  const { threadId } = useParams();

  return (
    <div className="grid h-full md:grid-cols-[18rem_1fr]">
      <aside className={cn('bg-card border-r', threadId ? 'hidden md:flex' : 'flex')}>
        <ThreadList className="w-full" />
      </aside>
      <div className={cn('min-h-0 flex-col', threadId ? 'flex' : 'hidden md:flex')}>
        {threadId ? (
          <>
            <Link
              to="/app/chat"
              className="text-muted-foreground flex items-center gap-1 border-b px-4 py-2 text-sm md:hidden"
            >
              <ArrowLeft className="h-4 w-4" /> Conversations
            </Link>
            <ChatPanel threadId={threadId} className="flex-1" />
          </>
        ) : (
          <p className="text-muted-foreground m-auto text-sm">
            Select a conversation or start a new one.
          </p>
        )}
      </div>
    </div>
  );
}
