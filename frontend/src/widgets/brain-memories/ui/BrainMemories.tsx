import { AlertCircle, Brain, ChevronDown, RotateCw, Search, SearchX } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { MemoryCard, useMemories, useMemorySearch, memoryKindSchema } from '@/entities/memory';
import type { MemoryKind } from '@/entities/memory';
import { AddMemoryForm, DeleteMemoryButton } from '@/features/manage-memory';
import { useDebounce } from '@/shared/hooks/use-debounce';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import { Skeleton } from '@/shared/ui/skeleton';

const SEARCH_DELAY_MS = 300;

interface StateProps {
  icon: React.ElementType;
  tone?: 'brand' | 'danger';
  title: string;
  description?: string;
  children?: React.ReactNode;
}

/** Centered empty/error block: icon, one line, optional explanation and actions. */
function State({ icon: Icon, tone = 'brand', title, description, children }: StateProps) {
  return (
    <div
      role={tone === 'danger' ? 'alert' : undefined}
      className="bg-card/60 flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border border-dashed px-6 py-10 text-center"
    >
      <span
        className={cn(
          'flex size-11 items-center justify-center rounded-full',
          tone === 'danger' ? 'bg-danger-bg text-danger-fg' : 'bg-brand-bg text-brand-ink',
        )}
      >
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="flex max-w-md flex-col gap-1">
        <p className="font-medium">{title}</p>
        {description && <p className="text-muted-foreground text-sm">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export function BrainMemories() {
  const { t } = useTranslation('brain');
  const [kind, setKind] = useState<MemoryKind | null>(null);
  const [search, setSearch] = useState('');
  const query = useDebounce(search.trim(), SEARCH_DELAY_MS);
  const searching = query.length > 0;

  const listed = useMemories(kind);
  const found = useMemorySearch(query);
  const active = searching ? found : listed;
  const { data, isLoading, isError, isPlaceholderData, refetch } = active;
  // search is semantic across kinds, so the kind filter narrows its results client-side
  const memories = searching && kind ? data?.filter((m) => m.kind === kind) : data;

  return (
    <div className="flex flex-col gap-6">
      <AddMemoryForm />

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative sm:w-48 sm:shrink-0">
            <select
              aria-label={t('memories.filter.kindLabel')}
              className="border-input bg-elevated focus-visible:border-brand focus-visible:ring-brand/25 h-11 w-full appearance-none rounded-[var(--radius-md)] border pr-9 pl-3 text-base transition-[border-color,box-shadow] focus-visible:ring-4 focus-visible:outline-none md:h-10 md:text-sm"
              value={kind ?? ''}
              onChange={(e) => {
                setKind(e.target.value ? memoryKindSchema.parse(e.target.value) : null);
              }}
            >
              <option value="">{t('memories.filter.allKinds')}</option>
              {memoryKindSchema.options.map((option) => (
                <option key={option} value={option}>
                  {t(`kinds.${option}`)}
                </option>
              ))}
            </select>
            <ChevronDown
              className="text-faint pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2"
              aria-hidden
            />
          </div>
          <div className="relative flex-1">
            <Search
              className="text-faint pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
              aria-hidden
            />
            <Input
              type="search"
              aria-label={t('memories.filter.searchLabel')}
              placeholder={t('memories.filter.searchPlaceholder')}
              className="h-11 pl-9 md:h-10"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
              }}
            />
          </div>
        </div>

        {memories && memories.length > 0 && (
          <p className="text-muted-foreground text-xs" aria-live="polite">
            {t('memories.count', { count: memories.length })}
          </p>
        )}
      </div>

      {isLoading && (
        <div className="flex flex-col gap-2" role="status" aria-busy="true">
          <span className="sr-only">{t('common:actions.loading')}</span>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[4.5rem] w-full rounded-[var(--radius-lg)]" />
          ))}
        </div>
      )}

      {isError && (
        <State icon={AlertCircle} tone="danger" title={t('memories.loadError')}>
          <Button
            variant="outline"
            onClick={() => {
              void refetch();
            }}
          >
            <RotateCw aria-hidden />
            {t('common:actions.retry')}
          </Button>
        </State>
      )}

      {memories?.length === 0 &&
        (searching ? (
          <State
            icon={SearchX}
            title={t('memories.empty.searchTitle')}
            description={t('memories.empty.searchDescription')}
          >
            <Button
              variant="outline"
              onClick={() => {
                setSearch('');
              }}
            >
              {t('memories.empty.clearSearch')}
            </Button>
          </State>
        ) : kind ? (
          <State
            icon={Brain}
            title={t('memories.empty.kindTitle')}
            description={t('memories.empty.kindDescription')}
          >
            <Button
              variant="outline"
              onClick={() => {
                setKind(null);
              }}
            >
              {t('memories.empty.showAll')}
            </Button>
          </State>
        ) : (
          <State
            icon={Brain}
            title={t('memories.empty.title')}
            description={t('memories.empty.description')}
          >
            <Button asChild variant="outline">
              <Link to="/app/chat">{t('memories.empty.openChat')}</Link>
            </Button>
          </State>
        ))}

      {memories && memories.length > 0 && (
        <ul
          className={cn(
            'flex flex-col gap-2 transition-opacity',
            isPlaceholderData && 'opacity-60',
          )}
          aria-busy={isPlaceholderData}
        >
          {memories.map((memory) => (
            <li key={memory.id} className="animate-fade-in">
              <MemoryCard memory={memory} actions={<DeleteMemoryButton memoryId={memory.id} />} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
