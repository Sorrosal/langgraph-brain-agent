import { RotateCw } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useThreadHistory } from '@/entities/checkpoint';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';
import { cn } from '@/shared/lib/cn';
import { formatDate, formatRelativeTime } from '@/shared/lib/format';

interface CheckpointTimelineProps {
  threadId: string;
}

/** Graph node names stay as code identifiers. */
function Nodes({ items }: { items: string[] }) {
  return <span className="font-mono text-xs">{items.length ? items.join(', ') : '—'}</span>;
}

/** Checkpoints, newest first, with the selected one's metadata alongside. */
export function CheckpointTimeline({ threadId }: CheckpointTimelineProps) {
  const { t } = useTranslation('inspector');
  const { data, isLoading, isError, refetch } = useThreadHistory(threadId);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
        <Skeleton className="hidden h-48 w-full rounded-[var(--radius-lg)] lg:block" />
      </div>
    );
  }
  if (isError) {
    return (
      <div
        role="alert"
        className="border-danger-border bg-danger-bg text-danger-fg flex flex-wrap items-center gap-3 rounded-[var(--radius-lg)] border p-4 text-sm"
      >
        <span className="flex-1">{t('timeline.loadFailed')}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            void refetch();
          }}
        >
          <RotateCw />
          {t('common:actions.retry')}
        </Button>
      </div>
    );
  }
  if (!data?.length) return <p className="text-muted-foreground text-sm">{t('timeline.empty')}</p>;

  const selected = data.find((c) => c.checkpoint_id === selectedId) ?? data[0];

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
      <ol
        aria-label={t('timeline.label')}
        className="before:bg-border relative flex flex-col gap-2 before:absolute before:top-4 before:bottom-4 before:left-[0.4375rem] before:w-px"
      >
        {data.map((checkpoint) => {
          const isSelected = checkpoint === selected;
          return (
            <li key={checkpoint.checkpoint_id} className="relative pl-7">
              <span
                aria-hidden="true"
                className={cn(
                  'ring-background absolute top-4 left-0 size-3.5 rounded-full border-2 ring-4',
                  isSelected ? 'border-primary bg-primary' : 'border-input bg-background',
                )}
              />
              <button
                type="button"
                aria-current={isSelected}
                onClick={() => {
                  setSelectedId(checkpoint.checkpoint_id);
                }}
                className={cn(
                  'flex min-h-11 w-full flex-wrap items-center gap-x-4 gap-y-1 rounded-[var(--radius-md)] border px-3 py-2 text-left text-sm transition-colors',
                  isSelected ? 'border-brand/30 bg-accent' : 'hover:bg-muted',
                )}
              >
                <span className="font-mono">{checkpoint.checkpoint_id.slice(0, 8)}</span>
                <Badge variant="outline">{t('timeline.step', { step: checkpoint.step })}</Badge>
                <span className="text-muted-foreground">
                  {checkpoint.created_at ? formatRelativeTime(checkpoint.created_at) : '—'}
                </span>
                <span>
                  {t('timeline.wrote')} <Nodes items={checkpoint.writes} />
                </span>
                <span>
                  {t('timeline.next')} <Nodes items={checkpoint.next} />
                </span>
                <span className="text-muted-foreground ml-auto">
                  {t('timeline.messages', { count: checkpoint.message_count })}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      {selected && (
        <Card className="h-fit lg:sticky lg:top-4" aria-label={t('timeline.details')}>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t('timeline.details')}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">{t('timeline.id')}</dt>
              <dd className="font-mono text-xs break-all">{selected.checkpoint_id}</dd>
              <dt className="text-muted-foreground">{t('timeline.source')}</dt>
              <dd className="font-mono text-xs">{selected.source}</dd>
              <dt className="text-muted-foreground">{t('timeline.stepLabel')}</dt>
              <dd>{selected.step}</dd>
              <dt className="text-muted-foreground">{t('timeline.created')}</dt>
              <dd>
                {selected.created_at
                  ? formatDate(selected.created_at, { dateStyle: 'medium', timeStyle: 'medium' })
                  : '—'}
              </dd>
              <dt className="text-muted-foreground">{t('timeline.wroteLabel')}</dt>
              <dd>
                <Nodes items={selected.writes} />
              </dd>
              <dt className="text-muted-foreground">{t('timeline.nextLabel')}</dt>
              <dd>
                <Nodes items={selected.next} />
              </dd>
              <dt className="text-muted-foreground">{t('timeline.messagesLabel')}</dt>
              <dd>{selected.message_count}</dd>
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
