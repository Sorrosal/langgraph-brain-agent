import { ChevronDown, Info, Microscope, RotateCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useThreads } from '@/entities/thread';
import { formatRelativeTime } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/skeleton';
import {
  CheckpointTimeline,
  ContextReport,
  ThreadStateSummary,
} from '@/widgets/checkpoint-timeline';

export default function InspectorPage() {
  const { t } = useTranslation('inspector');
  const { threadId } = useParams();
  const navigate = useNavigate();
  const { data: threads, isLoading, isError, refetch } = useThreads();
  const hasNoThreads = threads?.length === 0;

  return (
    <div className="animate-fade-in mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 sm:p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="text-muted-foreground mt-1 text-sm">{t('subtitle')}</p>
      </header>

      <div
        role="note"
        className="border-info-border bg-info-bg text-info-fg flex items-start gap-3 rounded-[var(--radius-lg)] border p-4 text-sm"
      >
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>{t('explainer')}</p>
      </div>

      <div className="flex flex-col gap-1.5 sm:max-w-sm">
        <label htmlFor="inspector-conversation" className="text-sm font-medium">
          {t('conversation.label')}
        </label>
        {isLoading ? (
          <Skeleton className="h-11 w-full md:h-10" />
        ) : (
          <div className="relative">
            <select
              id="inspector-conversation"
              className="border-input bg-elevated text-foreground focus-visible:border-brand focus-visible:ring-brand/25 h-11 w-full appearance-none rounded-[var(--radius-md)] border pr-9 pl-3 text-base transition-[border-color,box-shadow] focus-visible:ring-4 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:h-10 md:text-sm"
              value={threadId ?? ''}
              disabled={isError || hasNoThreads}
              onChange={(e) => {
                void navigate(`/app/inspector/${e.target.value}`);
              }}
            >
              <option value="" disabled>
                {t('conversation.placeholder')}
              </option>
              {threads?.map((thread) => (
                <option key={thread.id} value={thread.id}>
                  {`${thread.title || t('conversation.untitled')} · ${formatRelativeTime(thread.updated_at)}`}
                </option>
              ))}
            </select>
            <ChevronDown
              className="text-faint pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2"
              aria-hidden="true"
            />
          </div>
        )}
        {isError && (
          <div role="alert" className="text-danger-fg flex flex-wrap items-center gap-2 text-sm">
            <span>{t('conversation.loadFailed')}</span>
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
        )}
      </div>

      {threadId ? (
        <>
          <ThreadStateSummary threadId={threadId} />
          <ContextReport threadId={threadId} />
          <CheckpointTimeline key={threadId} threadId={threadId} />
        </>
      ) : (
        !isLoading &&
        !isError && (
          <div className="border-border flex flex-col items-center gap-2 rounded-[var(--radius-lg)] border border-dashed px-6 py-14 text-center">
            <span className="bg-brand-bg text-brand-ink mb-1 flex size-12 items-center justify-center rounded-full">
              <Microscope className="size-6" aria-hidden="true" />
            </span>
            <h2 className="text-base font-semibold">{t('empty.title')}</h2>
            <p className="text-muted-foreground max-w-sm text-sm">
              {hasNoThreads ? t('conversation.none') : t('empty.description')}
            </p>
            {hasNoThreads && (
              <Button asChild variant="outline" size="sm" className="mt-2">
                <Link to="/app/chat">{t('conversation.startOne')}</Link>
              </Button>
            )}
          </div>
        )
      )}
    </div>
  );
}
