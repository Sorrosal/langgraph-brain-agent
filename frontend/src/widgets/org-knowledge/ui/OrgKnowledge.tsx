import { AlertCircle, Building2, Info, RotateCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useOrgKnowledge } from '@/entities/memory';
import type { Memory } from '@/entities/memory';
import { selectIsAdmin, useAuthStore } from '@/features/auth';
import { AddOrgKnowledgeForm, DeleteOrgKnowledgeButton } from '@/features/manage-org-knowledge';
import { formatDate, formatRelativeTime } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { Card, CardContent } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';

function KnowledgeCard({ item, actions }: { item: Memory; actions?: React.ReactNode }) {
  const { t } = useTranslation('brain');
  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <time
            dateTime={item.created_at}
            title={t('org.card.createdAt', {
              date: formatDate(item.created_at, { dateStyle: 'medium', timeStyle: 'short' }),
            })}
            className="text-muted-foreground text-xs"
          >
            {formatRelativeTime(item.created_at)}
          </time>
          <p className="text-reading break-words whitespace-pre-wrap">{item.text}</p>
        </div>
        {actions}
      </CardContent>
    </Card>
  );
}

/** Facts shared with every user's agent. Everyone reads; only admins write. */
export function OrgKnowledge() {
  const { t } = useTranslation('brain');
  const isAdmin = useAuthStore(selectIsAdmin);
  const { data, isLoading, isError, refetch } = useOrgKnowledge();

  return (
    <div className="flex flex-col gap-6">
      <p className="text-muted-foreground text-sm">{t('org.description')}</p>

      {isAdmin ? (
        <AddOrgKnowledgeForm />
      ) : (
        <div className="bg-muted/60 text-muted-foreground flex items-start gap-2.5 rounded-[var(--radius-lg)] border p-3.5 text-sm">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>{t('org.readOnlyNote')}</p>
        </div>
      )}

      {isLoading && (
        <div className="flex flex-col gap-2" role="status" aria-busy="true">
          <span className="sr-only">{t('common:actions.loading')}</span>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[4.5rem] w-full rounded-[var(--radius-lg)]" />
          ))}
        </div>
      )}

      {isError && (
        <div
          role="alert"
          className="bg-card/60 flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border border-dashed px-6 py-10 text-center"
        >
          <span className="bg-danger-bg text-danger-fg flex size-11 items-center justify-center rounded-full">
            <AlertCircle className="size-5" aria-hidden />
          </span>
          <p className="font-medium">{t('org.loadError')}</p>
          <Button
            variant="outline"
            onClick={() => {
              void refetch();
            }}
          >
            <RotateCw aria-hidden />
            {t('common:actions.retry')}
          </Button>
        </div>
      )}

      {data?.length === 0 && (
        <div className="bg-card/60 flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border border-dashed px-6 py-10 text-center">
          <span className="bg-brand-bg text-brand-ink flex size-11 items-center justify-center rounded-full">
            <Building2 className="size-5" aria-hidden />
          </span>
          <div className="flex max-w-md flex-col gap-1">
            <p className="font-medium">{t('org.empty.title')}</p>
            <p className="text-muted-foreground text-sm">
              {t(isAdmin ? 'org.empty.descriptionAdmin' : 'org.empty.description')}
            </p>
          </div>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-muted-foreground text-xs" aria-live="polite">
            {t('org.count', { count: data.length })}
          </p>
          <ul className="flex flex-col gap-2">
            {data.map((item) => (
              <li key={item.id} className="animate-fade-in">
                <KnowledgeCard
                  item={item}
                  actions={isAdmin ? <DeleteOrgKnowledgeButton itemId={item.id} /> : undefined}
                />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
