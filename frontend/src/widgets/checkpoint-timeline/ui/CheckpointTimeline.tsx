import { useState } from 'react';
import { useThreadHistory } from '@/entities/checkpoint';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';
import { cn } from '@/shared/lib/cn';
import { formatRelativeTime } from '@/shared/lib/format';

interface CheckpointTimelineProps {
  threadId: string;
}

function list(items: string[]): string {
  return items.length ? items.join(', ') : '—';
}

/** Checkpoints, newest first, with the selected one's metadata alongside. */
export function CheckpointTimeline({ threadId }: CheckpointTimelineProps) {
  const { data, isLoading, isError } = useThreadHistory(threadId);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (isLoading) return <Skeleton className="h-48 w-full" />;
  if (isError) return <p className="text-destructive text-sm">Could not load the history.</p>;
  if (!data?.length) return <p className="text-muted-foreground text-sm">No checkpoints yet.</p>;

  const selected = data.find((c) => c.checkpoint_id === selectedId) ?? data[0];

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
      <ol aria-label="Checkpoints" className="flex flex-col gap-1">
        {data.map((checkpoint) => (
          <li key={checkpoint.checkpoint_id}>
            <button
              type="button"
              aria-current={checkpoint === selected}
              onClick={() => {
                setSelectedId(checkpoint.checkpoint_id);
              }}
              className={cn(
                'flex w-full flex-wrap items-center gap-x-4 gap-y-1 rounded-md border px-3 py-2 text-left text-sm',
                checkpoint === selected ? 'bg-accent' : 'hover:bg-accent/50',
              )}
            >
              <span className="font-mono">{checkpoint.checkpoint_id.slice(0, 8)}</span>
              <Badge variant="outline">step {checkpoint.step}</Badge>
              <span className="text-muted-foreground">
                {checkpoint.created_at ? formatRelativeTime(checkpoint.created_at) : '—'}
              </span>
              <span>wrote: {list(checkpoint.writes)}</span>
              <span>next: {list(checkpoint.next)}</span>
              <span className="text-muted-foreground ml-auto">{checkpoint.message_count} msg</span>
            </button>
          </li>
        ))}
      </ol>
      {selected && (
        <Card className="h-fit" aria-label="Checkpoint details">
          <CardHeader>
            <CardTitle className="text-base">Checkpoint details</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted-foreground">ID</dt>
              <dd className="font-mono break-all">{selected.checkpoint_id}</dd>
              <dt className="text-muted-foreground">Source</dt>
              <dd>{selected.source}</dd>
              <dt className="text-muted-foreground">Step</dt>
              <dd>{selected.step}</dd>
              <dt className="text-muted-foreground">Created</dt>
              <dd>{selected.created_at ?? '—'}</dd>
              <dt className="text-muted-foreground">Wrote</dt>
              <dd>{list(selected.writes)}</dd>
              <dt className="text-muted-foreground">Next</dt>
              <dd>{list(selected.next)}</dd>
              <dt className="text-muted-foreground">Messages</dt>
              <dd>{selected.message_count}</dd>
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
