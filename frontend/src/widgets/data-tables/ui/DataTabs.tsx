import { useState } from 'react';
import { useContacts } from '@/entities/contact';
import { dealStageSchema, useDeals } from '@/entities/deal';
import type { DealStage } from '@/entities/deal';
import { emailFolderSchema, useEmails } from '@/entities/email';
import type { EmailFolder } from '@/entities/email';
import { taskStatusSchema, useTasks } from '@/entities/task';
import type { TaskStatus } from '@/entities/task';
import { useDebounce } from '@/shared/hooks/use-debounce';
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
    <Input
      type="search"
      aria-label={label}
      placeholder={label}
      className="sm:max-w-xs"
      value={value}
      onChange={(e) => {
        onChange(e.target.value);
      }}
    />
  );
}

interface FilterSelectProps {
  label: string;
  value: string;
  options: readonly string[];
  allLabel?: string;
  onChange: (value: string) => void;
}

function FilterSelect({ label, value, options, allLabel, onChange }: FilterSelectProps) {
  return (
    <select
      aria-label={label}
      className="border-input bg-background h-9 rounded-md border px-2 text-sm"
      value={value}
      onChange={(e) => {
        onChange(e.target.value);
      }}
    >
      {allLabel && <option value="">{allLabel}</option>}
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  );
}

export function ContactsTab() {
  const [search, setSearch] = useState('');
  const query = useContacts(useDebounce(search.trim(), SEARCH_DELAY_MS));
  return (
    <div className="flex flex-col gap-3">
      <SearchBox label="Search contacts" value={search} onChange={setSearch} />
      <DataTable
        label="contacts"
        rows={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        rowKey={(c) => c.id}
        columns={[
          { header: 'Name', cell: (c) => c.name },
          { header: 'Email', cell: (c) => c.email },
          { header: 'Company', cell: (c) => c.company },
          { header: 'Phone', cell: (c) => c.phone ?? '—' },
          {
            header: 'Tags',
            cell: (c) => (
              <span className="flex flex-wrap gap-1">
                {c.tags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </span>
            ),
          },
        ]}
      />
    </div>
  );
}

export function DealsTab() {
  const [stage, setStage] = useState<DealStage | ''>('');
  const query = useDeals(stage);
  return (
    <div className="flex flex-col gap-3">
      <FilterSelect
        label="Filter by stage"
        value={stage}
        options={dealStageSchema.options}
        allLabel="All stages"
        onChange={(v) => {
          setStage(v === '' ? '' : dealStageSchema.parse(v));
        }}
      />
      <DataTable
        label="deals"
        rows={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        rowKey={(d) => d.id}
        columns={[
          { header: 'Title', cell: (d) => d.title },
          { header: 'Amount', cell: (d) => formatCurrency(d.amount, d.currency) },
          { header: 'Stage', cell: (d) => <Badge variant="secondary">{d.stage}</Badge> },
          { header: 'Updated', cell: (d) => formatDate(d.updated_at) },
        ]}
      />
    </div>
  );
}

export function TasksTab() {
  const [status, setStatus] = useState<TaskStatus | ''>('');
  const query = useTasks(status);
  return (
    <div className="flex flex-col gap-3">
      <FilterSelect
        label="Filter by status"
        value={status}
        options={taskStatusSchema.options}
        allLabel="All statuses"
        onChange={(v) => {
          setStatus(v === '' ? '' : taskStatusSchema.parse(v));
        }}
      />
      <DataTable
        label="tasks"
        rows={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        rowKey={(t) => t.id}
        columns={[
          { header: 'Title', cell: (t) => t.title },
          { header: 'Priority', cell: (t) => t.priority },
          { header: 'Status', cell: (t) => <Badge variant="secondary">{t.status}</Badge> },
          { header: 'Due', cell: (t) => (t.due_date ? formatDate(t.due_date) : '—') },
          { header: 'Assignee', cell: (t) => t.assignee ?? '—' },
        ]}
      />
    </div>
  );
}

export function EmailsTab() {
  const [folder, setFolder] = useState<EmailFolder>('inbox');
  const [search, setSearch] = useState('');
  const query = useEmails(folder, useDebounce(search.trim(), SEARCH_DELAY_MS));
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <FilterSelect
          label="Folder"
          value={folder}
          options={emailFolderSchema.options}
          onChange={(v) => {
            setFolder(emailFolderSchema.parse(v));
          }}
        />
        <SearchBox label="Search emails" value={search} onChange={setSearch} />
      </div>
      <DataTable
        label="emails"
        rows={query.data}
        isLoading={query.isLoading}
        isError={query.isError}
        rowKey={(e) => e.id}
        columns={[
          { header: 'From', cell: (e) => e.from_ },
          { header: 'To', cell: (e) => e.to.join(', ') },
          { header: 'Subject', cell: (e) => e.subject },
          {
            header: 'Date',
            cell: (e) => {
              const date = e.received_at ?? e.sent_at;
              return date ? formatDate(date) : '—';
            },
          },
        ]}
      />
    </div>
  );
}
