import { AlertCircle, Handshake, ListChecks, Mail, RotateCw, SearchX, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/skeleton';

export type DataEntity = 'contacts' | 'deals' | 'tasks' | 'emails';

const ICONS = {
  contacts: Users,
  deals: Handshake,
  tasks: ListChecks,
  emails: Mail,
} as const satisfies Record<DataEntity, React.ElementType>;

const FRAME = 'bg-card shadow-e1 overflow-hidden rounded-[var(--radius-lg)] border';

export interface Column<T> {
  header: string;
  cell: (row: T) => React.ReactNode;
  /** Numbers read better flush right. */
  align?: 'right';
}

interface DataTableProps<T> {
  entity: DataEntity;
  columns: readonly Column<T>[];
  rows: readonly T[] | undefined;
  rowKey: (row: T) => string;
  isLoading: boolean;
  isError: boolean;
  /** Showing the previous result while a new one loads. */
  isRefreshing?: boolean;
  /** A search or filter is narrowing the rows, so "empty" means "no match". */
  filtered?: boolean;
  onRetry: () => void;
}

interface StateProps {
  icon: React.ElementType;
  tone?: 'brand' | 'danger';
  title: string;
  description?: string;
  children?: React.ReactNode;
}

function State({ icon: Icon, tone = 'brand', title, description, children }: StateProps) {
  return (
    <div
      role={tone === 'danger' ? 'alert' : undefined}
      className="bg-card/60 flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border border-dashed px-6 py-12 text-center"
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

/** Responsive table (scrolls sideways on narrow screens) with loading, error and empty states. */
export function DataTable<T>({
  entity,
  columns,
  rows,
  rowKey,
  isLoading,
  isError,
  isRefreshing = false,
  filtered = false,
  onRetry,
}: DataTableProps<T>) {
  const { t } = useTranslation('data');

  if (isLoading) {
    return (
      <div className={FRAME} role="status" aria-busy="true">
        <span className="sr-only">{t('common:actions.loading')}</span>
        <div className="bg-subtle h-10 border-b" />
        {[0, 1, 2, 3, 4].map((row) => (
          <div key={row} className="flex gap-6 border-b px-4 py-3.5 last:border-b-0">
            {columns.map((column) => (
              <Skeleton key={column.header} className="h-4 flex-1" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <State icon={AlertCircle} tone="danger" title={t(`${entity}.error`)}>
        <Button variant="outline" onClick={onRetry}>
          <RotateCw aria-hidden />
          {t('common:actions.retry')}
        </Button>
      </State>
    );
  }

  if (!rows?.length) {
    return filtered ? (
      <State icon={SearchX} title={t(`${entity}.empty`)} description={t('table.emptyFiltered')} />
    ) : (
      <State
        icon={ICONS[entity]}
        title={t(`${entity}.empty`)}
        description={t('table.askAgent', { example: t(`${entity}.example`) })}
      >
        <Button asChild variant="outline">
          <Link to="/app/chat">{t('table.openChat')}</Link>
        </Button>
      </State>
    );
  }

  return (
    <div
      className={cn(FRAME, 'transition-opacity', isRefreshing && 'opacity-60')}
      aria-busy={isRefreshing}
    >
      {/* Focusable so keyboard users can scroll the table sideways on narrow screens. */}
      <div
        className="overflow-x-auto focus-visible:outline-2"
        tabIndex={0}
        role="region"
        aria-label={t(`${entity}.title`)}
      >
        <table className="w-full min-w-[40rem] text-left text-sm" aria-label={t(`${entity}.title`)}>
          <thead className="bg-subtle text-muted-foreground border-b">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.header}
                  scope="col"
                  className={cn(
                    'text-2xs px-4 py-2.5 font-semibold tracking-wide whitespace-nowrap uppercase',
                    column.align === 'right' && 'text-right',
                  )}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((row) => (
              <tr key={rowKey(row)} className="hover:bg-subtle/60 transition-colors">
                {columns.map((column) => (
                  <td
                    key={column.header}
                    className={cn(
                      'px-4 py-3 align-middle',
                      column.align === 'right' && 'text-right',
                    )}
                  >
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p
        className="text-muted-foreground bg-subtle/50 border-t px-4 py-2 text-xs"
        aria-live="polite"
      >
        {t(`${entity}.count`, { count: rows.length })}
      </p>
    </div>
  );
}
