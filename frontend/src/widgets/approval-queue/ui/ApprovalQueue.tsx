import { Link } from 'react-router-dom';
import { usePendingApprovals } from '@/entities/pending-approval';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';
import { formatRelativeTime } from '@/shared/lib/format';

export function ApprovalQueue() {
  const { data, isLoading, isError } = usePendingApprovals();

  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (isError) return <p className="text-destructive text-sm">Could not load pending approvals.</p>;
  if (!data?.length) {
    return <p className="text-muted-foreground text-sm">Nothing is waiting for your decision.</p>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {data.map(({ thread_id, title, updated_at, interrupt }) => (
        <li key={thread_id}>
          <Link to={`/app/chat/${thread_id}`} className="block">
            <Card className="hover:bg-accent/50 transition-colors">
              <CardContent className="flex flex-wrap items-center gap-3 p-4">
                <span className="min-w-0 flex-1 truncate font-medium">
                  {title || 'New conversation'}
                </span>
                <Badge variant={interrupt.kind === 'approval_required' ? 'default' : 'secondary'}>
                  {interrupt.kind === 'approval_required' ? 'approval' : 'uncertain'}
                </Badge>
                <span className="text-muted-foreground text-sm">
                  {interrupt.actions.length} action{interrupt.actions.length === 1 ? '' : 's'}
                </span>
                <span className="text-muted-foreground text-sm">
                  {formatRelativeTime(updated_at)}
                </span>
              </CardContent>
            </Card>
          </Link>
        </li>
      ))}
    </ul>
  );
}
