import { RotateCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useThread, type RunStatus } from '@/entities/thread';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';

interface ThreadStateSummaryProps {
  threadId: string;
}

const statusVariant = {
  idle: 'secondary',
  running: 'info',
  interrupted: 'warning',
  failed: 'destructive',
} as const satisfies Record<RunStatus, string>;

function cell(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** Current run status, rolling summary and the approvals audit trail of a thread. */
export function ThreadStateSummary({ threadId }: ThreadStateSummaryProps) {
  const { t } = useTranslation('inspector');
  const { data: thread, isLoading, isError, refetch } = useThread(threadId);

  if (isLoading) return <Skeleton className="h-36 w-full rounded-[var(--radius-lg)]" />;
  if (isError || !thread) {
    return (
      <div
        role="alert"
        className="border-danger-border bg-danger-bg text-danger-fg flex flex-wrap items-center gap-3 rounded-[var(--radius-lg)] border p-4 text-sm"
      >
        <span className="flex-1">{t('state.loadFailed')}</span>
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

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          {t('state.title')}{' '}
          <Badge variant={statusVariant[thread.run.status]}>
            {t(`state.status.${thread.run.status}`)}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 text-sm">
        {thread.run.error && (
          <p className="border-danger-border bg-danger-bg text-danger-fg rounded-[var(--radius-md)] border p-3 font-mono text-xs break-words">
            {thread.run.error}
          </p>
        )}
        <p className="text-reading max-w-prose">
          {thread.summary ?? <span className="text-muted-foreground">{t('state.noSummary')}</span>}
        </p>
        {thread.approvals.length === 0 ? (
          <p className="text-muted-foreground">{t('state.noApprovals')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left" aria-label={t('state.auditLabel')}>
              <thead className="text-muted-foreground text-xs">
                <tr>
                  <th className="py-1.5 pr-4 font-medium">{t('state.action')}</th>
                  <th className="py-1.5 pr-4 font-medium">{t('state.tool')}</th>
                  <th className="py-1.5 font-medium">{t('state.decision')}</th>
                </tr>
              </thead>
              <tbody>
                {thread.approvals.map((entry, index) => (
                  <tr key={`${cell(entry.action_id)}-${String(index)}`} className="border-t">
                    <td className="py-2 pr-4 font-mono text-xs">{cell(entry.action_id)}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{cell(entry.tool_name)}</td>
                    <td className="py-2">
                      {typeof entry.decision === 'string'
                        ? t(`state.decisions.${entry.decision}`, { defaultValue: entry.decision })
                        : cell(entry.decision)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
