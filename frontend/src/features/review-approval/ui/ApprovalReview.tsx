import {
  Check,
  CircleAlert,
  LoaderCircle,
  MessageSquare,
  Pencil,
  RotateCcw,
  ShieldAlert,
  SkipForward,
  X,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useId, useState } from 'react';
import type { ComponentProps, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ActionCard, useToolLabel } from '@/entities/approval';
import type {
  ActionRequest,
  ApprovalInterrupt,
  PendingInterrupt,
  UncertainAction,
  UncertainExecutionInterrupt,
} from '@/entities/approval';
import { cn } from '@/shared/lib/cn';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import { Textarea } from '@/shared/ui/textarea';
import { useSubmitReview } from '../api/review.api';
import { argsError, buildApprovalPayload, buildUncertainPayload } from '../model/review';
import type { ApprovalDraft, UncertainDraft } from '../model/review';

interface ApprovalReviewProps {
  threadId: string;
  interrupt: PendingInterrupt;
  /** Called before the decisions are sent, so the run is marked started first. */
  onSubmitting: () => void;
  onSubmitFailed: () => void;
}

type ButtonVariant = ComponentProps<typeof Button>['variant'];

interface OptionSpec<T extends string> {
  value: T;
  icon: LucideIcon;
  variant: ButtonVariant;
  selectedVariant?: ButtonVariant;
  /** Extra classes while not selected. */
  className?: string;
  /** Extra classes while selected. */
  selectedClassName?: string;
}

const QUIET = {
  variant: 'secondary',
  selectedClassName: 'bg-accent text-accent-foreground',
} as const;

// Approve is the primary path, Reject the destructive one, Edit/Respond stay quiet.
const APPROVAL_OPTIONS: readonly OptionSpec<ApprovalDraft['type']>[] = [
  { value: 'approve', icon: Check, variant: 'default' },
  {
    value: 'reject',
    icon: X,
    variant: 'outline',
    selectedVariant: 'destructive',
    className: 'border-danger-border text-danger-fg hover:bg-danger-bg hover:border-danger-border',
  },
  { value: 'edit', icon: Pencil, ...QUIET },
  { value: 'respond', icon: MessageSquare, ...QUIET },
];

// No option is suggested: only the person knows whether the tool really ran.
const UNCERTAIN_OPTIONS: readonly OptionSpec<UncertainDraft['type']>[] = [
  { value: 'confirm_done', icon: Check, ...QUIET },
  { value: 'retry', icon: RotateCcw, ...QUIET },
  { value: 'skip', icon: SkipForward, ...QUIET },
];

function DecisionGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly OptionSpec<T>[];
  value: T | undefined;
  onChange: (value: T) => void;
}) {
  const { t } = useTranslation('approvals');
  return (
    <div role="group" aria-label={label} className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
      {options.map((option) => {
        const selected = value === option.value;
        const Icon = selected ? Check : option.icon;
        return (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant={selected ? (option.selectedVariant ?? option.variant) : option.variant}
            aria-pressed={selected}
            className={cn(
              'max-sm:h-11 max-sm:text-sm',
              selected
                ? ['ring-brand ring-offset-card ring-2 ring-offset-2', option.selectedClassName]
                : [option.className, value !== undefined && 'opacity-70 hover:opacity-100'],
            )}
            onClick={() => {
              onChange(option.value);
            }}
          >
            <Icon aria-hidden />
            {t(`decisions.${option.value}`)}
          </Button>
        );
      })}
    </div>
  );
}

interface FieldControlProps {
  id: string;
  'aria-invalid': boolean;
  'aria-describedby': string | undefined;
}

/** Visible label, hint and inline error wired to a single control. */
function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: (props: FieldControlProps) => ReactNode;
}) {
  const id = useId();
  const describedBy =
    [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ') || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-medium">
        {label}
      </label>
      {children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': describedBy })}
      {hint && (
        <p id={`${id}-hint`} className="text-muted-foreground text-xs">
          {hint}
        </p>
      )}
      {error && (
        <p
          id={`${id}-error`}
          role="alert"
          className="text-danger-fg flex items-start gap-1.5 text-xs"
        >
          <CircleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      )}
    </div>
  );
}

function DecisionStatus({ decision }: { decision: string | undefined }) {
  const { t } = useTranslation('approvals');
  if (!decision) return <Badge variant="outline">{t('action.needsDecision')}</Badge>;
  return (
    <Badge>
      <Check className="size-3" aria-hidden />
      {t(`decisions.${decision}`)}
    </Badge>
  );
}

/** Frame shared by both reviews: heading, the cards, progress and the single submit button. */
function ReviewShell({
  kind,
  total,
  decided,
  isPending,
  error,
  onSubmit,
  children,
}: {
  kind: PendingInterrupt['kind'];
  total: number;
  decided: number;
  isPending: boolean;
  error: Error | null;
  onSubmit: () => void;
  children: ReactNode;
}) {
  const { t } = useTranslation('approvals');
  const headingId = useId();
  const complete = decided === total;
  const isApproval = kind === 'approval_required';

  let progress = t('review.progress', { done: decided, total });
  if (complete) progress = t('review.ready');
  else if (total === 1) progress = t('review.chooseOne');

  return (
    <section
      aria-labelledby={headingId}
      className="bg-card border-warning-border shadow-e2 motion-safe:animate-slide-up flex flex-col gap-4 rounded-[var(--radius-xl)] border p-4 sm:p-5"
    >
      <header className="flex items-start gap-3">
        <span
          aria-hidden
          className="bg-warning-bg text-warning-fg border-warning-border grid size-10 shrink-0 place-items-center rounded-full border"
        >
          <ShieldAlert className="size-5" />
        </span>
        <div className="min-w-0">
          <h2 id={headingId} className="text-base leading-snug font-semibold">
            {t(isApproval ? 'review.titleApproval' : 'review.titleUncertain')}
          </h2>
          <p className="text-muted-foreground mt-0.5 text-sm">
            {isApproval ? t('review.introApproval', { count: total }) : t('review.introUncertain')}
          </p>
        </div>
      </header>
      <fieldset disabled={isPending} className="m-0 flex min-w-0 flex-col gap-3 border-0 p-0">
        {children}
      </fieldset>
      {error && (
        <p
          role="alert"
          className="bg-danger-bg border-danger-border text-danger-fg flex items-start gap-2 rounded-[var(--radius-md)] border px-3 py-2 text-sm"
        >
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {t('review.sendFailed')}
            {error.message && (
              <span className="mt-0.5 block text-xs opacity-80">{error.message}</span>
            )}
          </span>
        </p>
      )}
      <footer className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-muted-foreground text-sm" aria-live="polite">
          {progress}
        </p>
        <Button
          type="button"
          className="max-sm:h-11 max-sm:w-full"
          disabled={!complete || isPending}
          aria-busy={isPending}
          onClick={onSubmit}
        >
          {isPending ? (
            <>
              <LoaderCircle className="motion-safe:animate-spin" aria-hidden />
              {t('review.sending')}
            </>
          ) : (
            t('review.submit')
          )}
        </Button>
      </footer>
    </section>
  );
}

function initialApprovalDraft(type: ApprovalDraft['type'], action: ActionRequest): ApprovalDraft {
  switch (type) {
    case 'approve':
      return { type };
    case 'reject':
      return { type, reason: '' };
    case 'respond':
      return { type, message: '' };
    case 'edit':
      return { type, argsText: JSON.stringify(action.args, null, 2) };
  }
}

interface FormProps<I> {
  threadId: string;
  interrupt: I;
  onSubmitting: () => void;
  onSubmitFailed: () => void;
}

function ApprovalForm({
  threadId,
  interrupt,
  onSubmitting,
  onSubmitFailed,
}: FormProps<ApprovalInterrupt>) {
  const { t } = useTranslation('approvals');
  const toolLabel = useToolLabel();
  const [drafts, setDrafts] = useState<Partial<Record<string, ApprovalDraft>>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { mutate, isPending, error } = useSubmitReview(threadId, 'approvals', {
    onSubmitting,
    onFailed: onSubmitFailed,
  });
  const decided = interrupt.actions.filter((action) => drafts[action.action_id]).length;

  function setDraft(id: string, draft: ApprovalDraft) {
    setDrafts((current) => ({ ...current, [id]: draft }));
    setErrors((current) => ({ ...current, [id]: '' }));
  }

  function submit() {
    const result = buildApprovalPayload(interrupt.actions, drafts);
    if (!result.ok) {
      setErrors(result.errors);
      return;
    }
    mutate(result.payload);
  }

  return (
    <ReviewShell
      kind={interrupt.kind}
      total={interrupt.actions.length}
      decided={decided}
      isPending={isPending}
      error={error}
      onSubmit={submit}
    >
      {interrupt.actions.map((action) => {
        const id = action.action_id;
        const draft = drafts[id];
        // Edited JSON is checked as you type; the other errors appear on submit.
        const liveError = draft?.type === 'edit' ? argsError(draft.argsText) : undefined;
        const fieldError = liveError ?? errors[id];
        return (
          <ActionCard key={id} action={action} status={<DecisionStatus decision={draft?.type} />}>
            <DecisionGroup
              label={t('decisions.decisionFor', { tool: toolLabel(action.tool_name) })}
              options={APPROVAL_OPTIONS}
              value={draft?.type}
              onChange={(type) => {
                setDraft(id, initialApprovalDraft(type, action));
              }}
            />
            {draft?.type === 'reject' && (
              <Field label={t('fields.rejectReason')} hint={t('fields.rejectHint')}>
                {(props) => (
                  <Input
                    {...props}
                    value={draft.reason}
                    onChange={(event) => {
                      setDraft(id, { type: 'reject', reason: event.target.value });
                    }}
                  />
                )}
              </Field>
            )}
            {draft?.type === 'edit' && (
              <Field label={t('fields.editArgs')} hint={t('fields.editHint')} error={fieldError}>
                {(props) => (
                  <Textarea
                    {...props}
                    className="font-mono leading-relaxed md:text-xs"
                    spellCheck={false}
                    rows={Math.min(14, Math.max(5, draft.argsText.split('\n').length + 1))}
                    value={draft.argsText}
                    onChange={(event) => {
                      setDraft(id, { type: 'edit', argsText: event.target.value });
                    }}
                  />
                )}
              </Field>
            )}
            {draft?.type === 'respond' && (
              <Field label={t('fields.respond')} hint={t('fields.respondHint')} error={fieldError}>
                {(props) => (
                  <Textarea
                    {...props}
                    rows={3}
                    value={draft.message}
                    onChange={(event) => {
                      setDraft(id, { type: 'respond', message: event.target.value });
                    }}
                  />
                )}
              </Field>
            )}
          </ActionCard>
        );
      })}
    </ReviewShell>
  );
}

function UncertainForm({
  threadId,
  interrupt,
  onSubmitting,
  onSubmitFailed,
}: FormProps<UncertainExecutionInterrupt>) {
  const { t } = useTranslation('approvals');
  const toolLabel = useToolLabel();
  const [drafts, setDrafts] = useState<Partial<Record<string, UncertainDraft>>>({});
  const { mutate, isPending, error } = useSubmitReview(threadId, 'uncertain', {
    onSubmitting,
    onFailed: onSubmitFailed,
  });
  const decided = interrupt.actions.filter((action) => drafts[action.action_id]).length;

  function setDraft(id: string, draft: UncertainDraft) {
    setDrafts((current) => ({ ...current, [id]: draft }));
  }

  function choose(action: UncertainAction, type: UncertainDraft['type']) {
    setDraft(action.action_id, type === 'confirm_done' ? { type, message: '' } : { type });
  }

  function submit() {
    const result = buildUncertainPayload(interrupt.actions, drafts);
    if (!result.ok) return;
    mutate(result.payload);
  }

  return (
    <ReviewShell
      kind={interrupt.kind}
      total={interrupt.actions.length}
      decided={decided}
      isPending={isPending}
      error={error}
      onSubmit={submit}
    >
      {interrupt.actions.map((action) => {
        const draft = drafts[action.action_id];
        return (
          <ActionCard
            key={action.action_id}
            action={action}
            status={<DecisionStatus decision={draft?.type} />}
          >
            <DecisionGroup
              label={t('decisions.decisionFor', { tool: toolLabel(action.tool_name) })}
              options={UNCERTAIN_OPTIONS}
              value={draft?.type}
              onChange={(type) => {
                choose(action, type);
              }}
            />
            {draft?.type === 'confirm_done' && (
              <Field label={t('fields.confirmResult')} hint={t('fields.confirmHint')}>
                {(props) => (
                  <Input
                    {...props}
                    value={draft.message}
                    onChange={(event) => {
                      setDraft(action.action_id, {
                        type: 'confirm_done',
                        message: event.target.value,
                      });
                    }}
                  />
                )}
              </Field>
            )}
          </ActionCard>
        );
      })}
    </ReviewShell>
  );
}

export function ApprovalReview({
  threadId,
  interrupt,
  onSubmitting,
  onSubmitFailed,
}: ApprovalReviewProps) {
  // A new interrupt (different actions) starts from a clean form instead of inheriting old drafts.
  const key = interrupt.actions.map((action) => action.action_id).join('|');
  return interrupt.kind === 'approval_required' ? (
    <ApprovalForm
      key={key}
      threadId={threadId}
      interrupt={interrupt}
      onSubmitting={onSubmitting}
      onSubmitFailed={onSubmitFailed}
    />
  ) : (
    <UncertainForm
      key={key}
      threadId={threadId}
      interrupt={interrupt}
      onSubmitting={onSubmitting}
      onSubmitFailed={onSubmitFailed}
    />
  );
}
