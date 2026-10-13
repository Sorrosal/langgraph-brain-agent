import { ChevronDown, Search } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContacts } from '@/entities/contact';
import { DealStageBadge, dealStageSchema, useDeals } from '@/entities/deal';
import type { DealStage } from '@/entities/deal';
import { emailFolderSchema, useEmails } from '@/entities/email';
import type { EmailFolder } from '@/entities/email';
import {
  TaskPriorityBadge,
  TaskStatusBadge,
  formatDueDate,
  isOverdue,
  taskStatusSchema,
  useTasks,
} from '@/entities/task';
import type { TaskStatus } from '@/entities/task';
import { useDebounce } from '@/shared/hooks/use-debounce';
import { cn } from '@/shared/lib/cn';
import { formatCurrency, formatDate } from '@/shared/lib/format';
import { Badge } from '@/shared/ui/badge';
import { Input } from '@/shared/ui/input';
import { DataTable } from './DataTable';

const SEARCH_DELAY_MS = 300;

interface SearchBoxProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

function SearchBox({ label, value, onChange }: SearchBoxProps) {
  return (
    <div className="relative flex-1 sm:max-w-xs">
      <Search
        className="text-faint pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
        aria-hidden
      />
      <Input
        type="search"
        aria-label={label}
        placeholder={label}
        className="h-11 pl-9 md:h-10"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
        }}
      />
    </div>
  );
}

interface FilterSelectProps {
  label: string;
  value: string;
  options: readonly { value: string; label: string }[];
  allLabel?: string;
  onChange: (value: string) => void;
}

function FilterSelect({ label, value, options, allLabel, onChange }: FilterSelectProps) {
  return (
    <div className="relative sm:w-48 sm:shrink-0">
      <select
        aria-label={label}
        className="border-input bg-elevated focus-visible:border-brand focus-visible:ring-brand/25 h-11 w-full appearance-none rounded-[var(--radius-md)] border pr-9 pl-3 text-base transition-[border-color,box-shadow] focus-visible:ring-4 focus-visible:outline-none md:h-10 md:text-sm"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
        }}
      >
        {allLabel && <option value="">{allLabel}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown
        className="text-faint pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2"
        aria-hidden
      />
    </div>
  );
}

/** Long values truncate with an ellipsis; the full text stays available on hover. */
function Truncated({ text, className }: { text: string; className?: string }) {
  return (
    <span className={cn('block max-w-[16rem] truncate', className)} title={text}>
      {text}
    </span>
  );
}

function Dash() {
  const { t } = useTranslation('data');
  return (
    <>
      <span className="text-faint" aria-hidden>
        —
      </span>
      <span className="sr-only">{t('table.none')}</span>
    </>
  );
}

const FILTER_BAR = 'flex flex-col gap-2 sm:flex-row sm:items-center';

export function ContactsTab() {
  const { t } = useTranslation('data');
  const [search, setSearch] = useState('');
  const term = useDebounce(search.trim(), SEARCH_DELAY_MS);
  const query = useContacts(term);
  return (
    <div className="flex flex-col gap-3">
      <div className={FILTER_BAR}>
        <SearchBox label={t('contacts.search')} value={search} onChange={setSearch} />
      </div>
      <DataTable
        entity="contacts"
        rows={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        isRefreshing={query.isPlaceholderData}
        filtered={term.length > 0}
        onRetry={() => void query.refetch()}
        rowKey={(c) => c.id}
        columns={[
          {
            header: t('contacts.columns.name'),
            cell: (c) => <Truncated text={c.name} className="font-medium" />,
          },
          {
            header: t('contacts.columns.email'),
            cell: (c) => (
              <a
                href={`mailto:${c.email}`}
                title={c.email}
                className="text-brand-ink block max-w-[16rem] truncate rounded-sm hover:underline"
              >
                {c.email}
              </a>
            ),
          },
          { header: t('contacts.columns.company'), cell: (c) => <Truncated text={c.company} /> },
          {
            header: t('contacts.columns.phone'),
            cell: (c) =>
              c.phone ? (
                <span className="whitespace-nowrap tabular-nums">{c.phone}</span>
              ) : (
                <Dash />
              ),
          },
          {
            header: t('contacts.columns.tags'),
            cell: (c) =>
              c.tags.length > 0 ? (
                <span className="flex max-w-[14rem] flex-wrap gap-1">
                  {c.tags.map((tag) => (
                    <Badge key={tag} variant="outline">
                      {tag}
                    </Badge>
                  ))}
                </span>
              ) : (
                <Dash />
              ),
          },
        ]}
      />
    </div>
  );
}

export function DealsTab() {
  const { t } = useTranslation('data');
  const [stage, setStage] = useState<DealStage | ''>('');
  const query = useDeals(stage);
  return (
    <div className="flex flex-col gap-3">
      <div className={FILTER_BAR}>
        <FilterSelect
          label={t('deals.filter')}
          value={stage}
          options={dealStageSchema.options.map((value) => ({
            value,
            label: t(`deals.stages.${value}`),
          }))}
          allLabel={t('deals.allStages')}
          onChange={(v) => {
            setStage(v === '' ? '' : dealStageSchema.parse(v));
          }}
        />
      </div>
      <DataTable
        entity="deals"
        rows={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        isRefreshing={query.isPlaceholderData}
        filtered={stage !== ''}
        onRetry={() => void query.refetch()}
        rowKey={(d) => d.id}
        columns={[
          {
            header: t('deals.columns.title'),
            cell: (d) => <Truncated text={d.title} className="font-medium" />,
          },
          {
            header: t('deals.columns.amount'),
            align: 'right',
            cell: (d) => (
              <span className="font-medium whitespace-nowrap tabular-nums">
                {formatCurrency(d.amount, d.currency)}
              </span>
            ),
          },
          { header: t('deals.columns.stage'), cell: (d) => <DealStageBadge stage={d.stage} /> },
          {
            header: t('deals.columns.updated'),
            cell: (d) => (
              <span className="text-muted-foreground whitespace-nowrap">
                {formatDate(d.updated_at)}
              </span>
            ),
          },
        ]}
      />
    </div>
  );
}

export function TasksTab() {
  const { t } = useTranslation('data');
  const [status, setStatus] = useState<TaskStatus | ''>('');
  const query = useTasks(status);
  return (
    <div className="flex flex-col gap-3">
      <div className={FILTER_BAR}>
        <FilterSelect
          label={t('tasks.filter')}
          value={status}
          options={taskStatusSchema.options.map((value) => ({
            value,
            label: t(`tasks.statuses.${value}`),
          }))}
          allLabel={t('tasks.allStatuses')}
          onChange={(v) => {
            setStatus(v === '' ? '' : taskStatusSchema.parse(v));
          }}
        />
      </div>
      <DataTable
        entity="tasks"
        rows={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        isRefreshing={query.isPlaceholderData}
        filtered={status !== ''}
        onRetry={() => void query.refetch()}
        rowKey={(task) => task.id}
        columns={[
          {
            header: t('tasks.columns.title'),
            cell: (task) => <Truncated text={task.title} className="font-medium" />,
          },
          {
            header: t('tasks.columns.priority'),
            cell: (task) => <TaskPriorityBadge priority={task.priority} />,
          },
          {
            header: t('tasks.columns.status'),
            cell: (task) => <TaskStatusBadge status={task.status} />,
          },
          {
            header: t('tasks.columns.due'),
            cell: (task) =>
              task.due_date ? (
                <span className="inline-flex items-center gap-2 whitespace-nowrap">
                  {formatDueDate(task.due_date)}
                  {isOverdue(task) && <Badge variant="destructive">{t('tasks.overdue')}</Badge>}
                </span>
              ) : (
                <Dash />
              ),
          },
          {
            header: t('tasks.columns.assignee'),
            cell: (task) => (task.assignee ? <Truncated text={task.assignee} /> : <Dash />),
          },
        ]}
      />
    </div>
  );
}

export function EmailsTab() {
  const { t } = useTranslation('data');
  const [folder, setFolder] = useState<EmailFolder>('inbox');
  const [search, setSearch] = useState('');
  const term = useDebounce(search.trim(), SEARCH_DELAY_MS);
  const query = useEmails(folder, term);
  return (
    <div className="flex flex-col gap-3">
      <div className={FILTER_BAR}>
        <FilterSelect
          label={t('emails.folder')}
          value={folder}
          options={emailFolderSchema.options.map((value) => ({
            value,
            label: t(`emails.folders.${value}`),
          }))}
          onChange={(v) => {
            setFolder(emailFolderSchema.parse(v));
          }}
        />
        <SearchBox label={t('emails.search')} value={search} onChange={setSearch} />
      </div>
      <DataTable
        entity="emails"
        rows={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        isRefreshing={query.isPlaceholderData}
        filtered={term.length > 0}
        onRetry={() => void query.refetch()}
        rowKey={(e) => e.id}
        columns={[
          { header: t('emails.columns.from'), cell: (e) => <Truncated text={e.from_} /> },
          {
            header: t('emails.columns.to'),
            cell: (e) => <Truncated text={e.to.join(', ')} />,
          },
          {
            header: t('emails.columns.subject'),
            cell: (e) => <Truncated text={e.subject} className="max-w-[22rem] font-medium" />,
          },
          {
            header: t('emails.columns.date'),
            cell: (e) => {
              const date = e.received_at ?? e.sent_at;
              return date ? (
                <span className="text-muted-foreground whitespace-nowrap">
                  {formatDate(date, { dateStyle: 'medium', timeStyle: 'short' })}
                </span>
              ) : (
                <Dash />
              );
            },
          },
        ]}
      />
    </div>
  );
}
