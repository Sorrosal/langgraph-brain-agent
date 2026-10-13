import { ChevronRight, CircleAlert, CircleHelp, ShieldCheck, ShieldAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { RiskBadge, useToolLabel } from '@/entities/approval';
import type { ActionRequest } from '@/entities/approval';
import { usePendingApprovals } from '@/entities/pending-approval';
import type { PendingApproval } from '@/entities/pending-approval';
import { formatRelativeTime } from '@/shared/lib/format';
import { Badge } from '@/shared/ui/badge';
import { Button, buttonVariants } from '@/shared/ui/button';
import { Card } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';

type Risk = ActionRequest['risk'];

const RISK_ORDER: readonly Risk[] = ['low', 'medium', 'high'];

const GROUPS = [
  { kind: 'approval_required', titleKey: 'queue.groupApproval', icon: ShieldAlert },
  { kind: 'uncertain_execution', titleKey: 'queue.groupUncertain', icon: CircleHelp },
] as const;

function highestRisk(actions: readonly ActionRequest[]): Risk {
  return actions.reduce<Risk>(
    (max, { risk }) => (RISK_ORDER.indexOf(risk) > RISK_ORDER.indexOf(max) ? risk : max),
    'low',
  );
}

function QueueItem({ item }: { item: PendingApproval }) {
  const { t } = useTranslation('approvals');
  const toolLabel = useToolLabel();
  const { thread_id, title, updated_at, interrupt } = item;
  const actions: readonly { tool_name: string }[] = interrupt.actions;
  const tools = [...new Set(actions.map((action) => toolLabel(action.tool_name)))].join(', ');

  return (
    <Link to={`/app/chat/${thread_id}`} className="group block rounded-[var(--radius-lg)]">
      <Card className="group-hover:border-brand/40 group-hover:shadow-e2 flex flex-wrap items-center gap-x-4 gap-y-2 p-4 transition-[border-color,box-shadow]">
        <div className="min-w-0 flex-1 basis-56">
          <p className="truncate font-medium">{title || t('queue.untitled')}</p>
          <p className="text-muted-foreground truncate text-sm">{tools}</p>
        </div>
        <div className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          {interrupt.kind === 'approval_required' && (
            <RiskBadge risk={highestRisk(interrupt.actions)} />
          )}
          <span>{t('queue.actions', { count: actions.length })}</span>
          <time dateTime={updated_at} className="whitespace-nowrap">
            {formatRelativeTime(updated_at)}
          </time>
          <ChevronRight
            className="text-faint size-4 transition-transform motion-safe:group-hover:translate-x-0.5"
            aria-hidden
          />
        </div>
      </Card>
    </Link>
  );
}

function QueueSkeleton() {
  const { t } = useTranslation();
  return (
    <div role="status" aria-busy="true" className="flex flex-col gap-2">
      <span className="sr-only">{t('actions.loading')}</span>
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-[4.5rem] w-full rounded-[var(--radius-lg)]" />
      ))}
    </div>
  );
}

function QueueEmpty() {
  const { t } = useTranslation('approvals');
  return (
    <div className="bg-card/60 flex flex-col items-center gap-3 rounded-[var(--radius-xl)] border border-dashed px-6 py-12 text-center">
      <span className="bg-success-bg text-success-fg border-success-border grid size-12 place-items-center rounded-full border">
        <ShieldCheck className="size-6" aria-hidden />
      </span>
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold">{t('queue.emptyTitle')}</h2>
        <p className="text-muted-foreground max-w-sm text-sm">{t('queue.emptyDescription')}</p>
      </div>
      <Link to="/app/chat" className={buttonVariants({ variant: 'outline' })}>
        {t('queue.emptyAction')}
      </Link>
    </div>
  );
}

export function ApprovalQueue() {
  const { t } = useTranslation('approvals');
  const { data, isLoading, isError, refetch } = usePendingApprovals();

  if (isLoading) return <QueueSkeleton />;
  if (isError) {
    return (
      <div
        role="alert"
        className="bg-danger-bg border-danger-border text-danger-fg flex flex-wrap items-center gap-3 rounded-[var(--radius-lg)] border p-4 text-sm"
      >
        <CircleAlert className="size-4 shrink-0" aria-hidden />
        <p className="min-w-0 flex-1">{t('queue.loadFailed')}</p>
        <Button
          size="sm"
          variant="outline"
          className="max-sm:h-11"
          onClick={() => {
            void refetch();
          }}
        >
          {t('common:actions.retry')}
        </Button>
      </div>
    );
  }
  if (!data?.length) return <QueueEmpty />;

  return (
    <div className="flex flex-col gap-6">
      {GROUPS.map(({ kind, titleKey, icon: Icon }) => {
        // Oldest first: whoever has waited longest is at the top.
        const items = data
          .filter((item) => item.interrupt.kind === kind)
          .sort((a, b) => Date.parse(a.updated_at) - Date.parse(b.updated_at));
        if (items.length === 0) return null;
        return (
          <section key={kind} aria-labelledby={`queue-${kind}`} className="flex flex-col gap-2">
            <h2
              id={`queue-${kind}`}
              className="text-muted-foreground flex items-center gap-2 text-sm font-semibold"
            >
              <Icon className="size-4" aria-hidden />
              {t(titleKey)}
              <Badge variant="secondary">{items.length}</Badge>
            </h2>
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <li key={item.thread_id}>
                  <QueueItem item={item} />
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
