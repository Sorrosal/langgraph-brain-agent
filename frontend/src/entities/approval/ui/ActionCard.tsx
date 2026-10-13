import {
  Brain,
  ChevronRight,
  FileText,
  Inbox,
  ListChecks,
  Mail,
  Trash2,
  Users,
  Wrench,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Fragment } from 'react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/shared/lib/cn';
import { useToolLabel } from '../lib/tool-label';
import type { ActionRequest, UncertainAction } from '../model/approval.types';
import { RiskBadge } from './RiskBadge';

interface ActionCardProps {
  action: ActionRequest | UncertainAction;
  /** Shown next to the risk badge, e.g. whether this action still needs a decision. */
  status?: ReactNode;
  /** Decision controls, rendered below a divider. */
  children?: ReactNode;
  className?: string;
}

const TOOL_ICONS: Partial<Record<string, LucideIcon>> = {
  send_email: Mail,
  read_email: Mail,
  search_inbox: Inbox,
  crm_search_contacts: Users,
  crm_get_contact: Users,
  crm_create_contact: Users,
  crm_list_deals: Users,
  crm_create_deal: Users,
  crm_update_deal: Users,
  crm_delete_record: Trash2,
  create_task: ListChecks,
  list_tasks: ListChecks,
  complete_task: ListChecks,
  delete_task: Trash2,
  remember: Brain,
  recall: Brain,
  read_rules: FileText,
  update_rules_file: FileText,
};

/** Longer or multi-line values get their own scrollable block. */
const INLINE_MAX = 80;

function humanizeKey(key: string): string {
  const spaced = key
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function ArgValue({ label, value }: { label: string; value: unknown }) {
  const { t } = useTranslation('approvals');
  if (value === null || value === undefined || value === '') {
    return <span className="text-faint">{t('values.empty')}</span>;
  }
  if (typeof value === 'boolean') return <span>{t(value ? 'values.true' : 'values.false')}</span>;
  // A list of plain values (e.g. email recipients) reads better as "a, b" than as a JSON block.
  const flat =
    Array.isArray(value) && value.every((item) => typeof item !== 'object' || item === null);
  const text =
    typeof value === 'string'
      ? value
      : flat
        ? value.map(String).join(', ')
        : JSON.stringify(value, null, 2);
  if ((flat || typeof value !== 'object') && text.length <= INLINE_MAX && !text.includes('\n')) {
    return <span className="break-words">{text}</span>;
  }
  return (
    <pre
      aria-label={label}
      tabIndex={0}
      className="bg-muted max-h-40 overflow-auto rounded-[var(--radius-sm)] p-2.5 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap"
    >
      {text}
    </pre>
  );
}

function ArgsList({ args }: { args: Record<string, unknown> }) {
  const { t } = useTranslation('approvals');
  const entries = Object.entries(args);
  return (
    <div className="flex flex-col gap-2">
      <p className="text-faint text-2xs font-semibold tracking-wide uppercase">
        {t('action.arguments')}
      </p>
      {entries.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t('action.noArguments')}</p>
      ) : (
        <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[minmax(6rem,9rem)_1fr]">
          {entries.map(([key, value]) => (
            <Fragment key={key}>
              <dt className="text-muted-foreground sm:pt-0.5">{humanizeKey(key)}</dt>
              <dd className="min-w-0">
                <ArgValue label={humanizeKey(key)} value={value} />
              </dd>
            </Fragment>
          ))}
        </dl>
      )}
      <details className="group">
        <summary className="text-muted-foreground hover:text-foreground flex min-h-11 w-fit cursor-pointer list-none items-center gap-1 text-xs font-medium select-none sm:min-h-8 [&::-webkit-details-marker]:hidden">
          <ChevronRight
            className="size-3.5 transition-transform group-open:rotate-90"
            aria-hidden
          />
          {t('action.rawJson')}
        </summary>
        <pre className="bg-muted max-h-48 overflow-auto rounded-[var(--radius-sm)] p-2.5 font-mono text-xs leading-relaxed">
          {JSON.stringify(args, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export function ActionCard({ action, status, children, className }: ActionCardProps) {
  const { t } = useTranslation('approvals');
  const toolLabel = useToolLabel();
  const label = toolLabel(action.tool_name);
  const Icon = TOOL_ICONS[action.tool_name] ?? Wrench;
  const risk = 'risk' in action ? action.risk : undefined;
  const isApproval = risk !== undefined;
  const explanation = 'reason' in action ? action.reason : action.message;

  return (
    <section
      aria-label={t('action.region', { tool: label })}
      className={cn(
        'bg-card shadow-e1 flex flex-col gap-3 rounded-[var(--radius-lg)] border p-4',
        className,
      )}
    >
      <header className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <span
          aria-hidden
          className="bg-brand-bg text-brand-ink grid size-9 shrink-0 place-items-center rounded-[var(--radius-md)]"
        >
          <Icon className="size-[18px]" />
        </span>
        <div className="min-w-40 flex-1">
          <h3 className="font-display text-base leading-snug font-semibold">{label}</h3>
          {label !== action.tool_name && (
            <code className="text-faint text-2xs font-mono">{action.tool_name}</code>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {risk && <RiskBadge risk={risk} />}
          {status}
        </div>
      </header>
      <div
        className={cn(
          'rounded-[var(--radius-md)] border px-3 py-2 text-sm',
          isApproval ? 'bg-subtle' : 'bg-warning-bg border-warning-border text-warning-fg',
        )}
      >
        <p className="text-2xs font-semibold tracking-wide uppercase opacity-70">
          {t(isApproval ? 'action.why' : 'action.outcome')}
        </p>
        <p className="mt-0.5">{explanation}</p>
      </div>
      <ArgsList args={action.args} />
      {children && <div className="flex flex-col gap-3 border-t pt-3">{children}</div>}
    </section>
  );
}
