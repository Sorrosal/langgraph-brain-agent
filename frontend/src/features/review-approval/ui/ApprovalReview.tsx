import { useState } from 'react';
import { ActionCard } from '@/entities/approval';
import type {
  ActionRequest,
  ApprovalInterrupt,
  PendingInterrupt,
  UncertainAction,
  UncertainExecutionInterrupt,
} from '@/entities/approval';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import { Textarea } from '@/shared/ui/textarea';
import { useSubmitReview } from '../api/review.api';
import { buildApprovalPayload, buildUncertainPayload } from '../model/review';
import type { ApprovalDraft, UncertainDraft } from '../model/review';

interface ApprovalReviewProps {
  threadId: string;
  interrupt: PendingInterrupt;
  /** The decisions were accepted and the run resumed. */
  onSubmitted: () => void;
}

interface Option<T extends string> {
  value: T;
  label: string;
}

interface DecisionGroupProps<T extends string> {
  label: string;
  options: readonly Option<T>[];
  value: T | undefined;
  onChange: (value: T) => void;
}

function DecisionGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: DecisionGroupProps<T>) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => (
        <Button
          key={option.value}
          type="button"
          size="sm"
          variant={value === option.value ? 'default' : 'outline'}
          aria-pressed={value === option.value}
          onClick={() => {
            onChange(option.value);
          }}
        >
          {option.label}
        </Button>
      ))}
    </div>
  );
}

function FieldError({ message }: { message: string | undefined }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-destructive text-sm">
      {message}
    </p>
  );
}

const APPROVAL_OPTIONS = [
  { value: 'approve', label: 'Approve' },
  { value: 'reject', label: 'Reject' },
  { value: 'edit', label: 'Edit' },
  { value: 'respond', label: 'Respond' },
] as const;

const UNCERTAIN_OPTIONS = [
  { value: 'confirm_done', label: 'Confirm done' },
  { value: 'retry', label: 'Retry' },
  { value: 'skip', label: 'Skip' },
] as const;

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

function ApprovalForm({
  threadId,
  interrupt,
  onSubmitted,
}: {
  threadId: string;
  interrupt: ApprovalInterrupt;
  onSubmitted: () => void;
}) {
  const [drafts, setDrafts] = useState<Partial<Record<string, ApprovalDraft>>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { mutate, isPending } = useSubmitReview(threadId, 'approvals');
  const complete = interrupt.actions.every((action) => drafts[action.action_id]);

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
    mutate(result.payload, { onSuccess: onSubmitted });
  }

  return (
    <>
      {interrupt.actions.map((action) => {
        const id = action.action_id;
        const draft = drafts[id];
        return (
          <ActionCard key={id} action={action}>
            <DecisionGroup
              label={`Decision for ${action.tool_name}`}
              options={APPROVAL_OPTIONS}
              value={draft?.type}
              onChange={(type) => {
                setDraft(id, initialApprovalDraft(type, action));
              }}
            />
            {draft?.type === 'reject' && (
              <Input
                aria-label="Reason (optional)"
                value={draft.reason}
                onChange={(event) => {
                  setDraft(id, { type: 'reject', reason: event.target.value });
                }}
              />
            )}
            {draft?.type === 'edit' && (
              <Textarea
                aria-label="Arguments (JSON)"
                className="font-mono text-xs"
                rows={5}
                value={draft.argsText}
                onChange={(event) => {
                  setDraft(id, { type: 'edit', argsText: event.target.value });
                }}
              />
            )}
            {draft?.type === 'respond' && (
              <Textarea
                aria-label="Response to the assistant"
                rows={3}
                value={draft.message}
                onChange={(event) => {
                  setDraft(id, { type: 'respond', message: event.target.value });
                }}
              />
            )}
            <FieldError message={errors[id]} />
          </ActionCard>
        );
      })}
      <Button type="button" disabled={!complete || isPending} onClick={submit}>
        Submit decisions
      </Button>
    </>
  );
}

function UncertainForm({
  threadId,
  interrupt,
  onSubmitted,
}: {
  threadId: string;
  interrupt: UncertainExecutionInterrupt;
  onSubmitted: () => void;
}) {
  const [drafts, setDrafts] = useState<Partial<Record<string, UncertainDraft>>>({});
  const { mutate, isPending } = useSubmitReview(threadId, 'uncertain');
  const complete = interrupt.actions.every((action) => drafts[action.action_id]);

  function setDraft(id: string, draft: UncertainDraft) {
    setDrafts((current) => ({ ...current, [id]: draft }));
  }

  function choose(action: UncertainAction, type: UncertainDraft['type']) {
    setDraft(action.action_id, type === 'confirm_done' ? { type, message: '' } : { type });
  }

  function submit() {
    const result = buildUncertainPayload(interrupt.actions, drafts);
    if (result.ok) mutate(result.payload, { onSuccess: onSubmitted });
  }

  return (
    <>
      {interrupt.actions.map((action) => {
        const draft = drafts[action.action_id];
        return (
          <ActionCard key={action.action_id} action={action}>
            <DecisionGroup
              label={`Decision for ${action.tool_name}`}
              options={UNCERTAIN_OPTIONS}
              value={draft?.type}
              onChange={(type) => {
                choose(action, type);
              }}
            />
            {draft?.type === 'confirm_done' && (
              <Input
                aria-label="Result to report (optional)"
                value={draft.message}
                onChange={(event) => {
                  setDraft(action.action_id, { type: 'confirm_done', message: event.target.value });
                }}
              />
            )}
          </ActionCard>
        );
      })}
      <Button type="button" disabled={!complete || isPending} onClick={submit}>
        Submit decisions
      </Button>
    </>
  );
}

export function ApprovalReview({ threadId, interrupt, onSubmitted }: ApprovalReviewProps) {
  const title =
    interrupt.kind === 'approval_required'
      ? 'Waiting for your approval'
      : 'These actions may already have run. What happened?';

  return (
    <div className="bg-card flex flex-col gap-3 rounded-lg border-2 border-amber-500/60 p-3">
      <h2 className="text-sm font-semibold">{title}</h2>
      {interrupt.kind === 'approval_required' ? (
        <ApprovalForm threadId={threadId} interrupt={interrupt} onSubmitted={onSubmitted} />
      ) : (
        <UncertainForm threadId={threadId} interrupt={interrupt} onSubmitted={onSubmitted} />
      )}
    </div>
  );
}
