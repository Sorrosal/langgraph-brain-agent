import { z } from 'zod';
import { i18n } from '@/shared/i18n';
import type {
  ActionRequest,
  ApprovalDecision,
  ApprovalResponse,
  UncertainAction,
  UncertainDecision,
  UncertainResponse,
} from '@/entities/approval';

export type ApprovalDraft =
  | { type: 'approve' }
  | { type: 'reject'; reason: string }
  | { type: 'edit'; argsText: string }
  | { type: 'respond'; message: string };

export type UncertainDraft =
  | { type: 'confirm_done'; message: string }
  | { type: 'retry' }
  | { type: 'skip' };

export type BuildResult<T> =
  | { ok: true; payload: T }
  | { ok: false; errors: Record<string, string> };

const argsSchema = z.record(z.string(), z.unknown());

// User-facing messages are resolved at call time so they follow the active language.
function parseArgs(text: string): { args: Record<string, unknown> } | { error: string } {
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    return { error: i18n.t('approvals:errors.invalidJson') };
  }
  const parsed = argsSchema.safeParse(json);
  return parsed.success ? { args: parsed.data } : { error: i18n.t('approvals:errors.notObject') };
}

/** Message for edited arguments that cannot be sent, or `undefined` when they are valid. */
export function argsError(text: string): string | undefined {
  const result = parseArgs(text);
  return 'error' in result ? result.error : undefined;
}

function toApprovalDecision(draft: ApprovalDraft): ApprovalDecision | string {
  switch (draft.type) {
    case 'approve':
      return { type: 'approve' };
    case 'reject':
      return draft.reason.trim()
        ? { type: 'reject', reason: draft.reason.trim() }
        : { type: 'reject' };
    case 'respond':
      return draft.message.trim()
        ? { type: 'respond', message: draft.message.trim() }
        : i18n.t('approvals:errors.emptyResponse');
    case 'edit': {
      const result = parseArgs(draft.argsText);
      return 'error' in result ? result.error : { type: 'edit', args: result.args };
    }
  }
}

function toUncertainDecision(draft: UncertainDraft): UncertainDecision {
  if (draft.type !== 'confirm_done') return { type: draft.type };
  return draft.message.trim()
    ? { type: 'confirm_done', message: draft.message.trim() }
    : { type: 'confirm_done' };
}

/** One decision per action, keyed by action id; reports every problem at once. */
export function buildApprovalPayload(
  actions: readonly ActionRequest[],
  drafts: Partial<Record<string, ApprovalDraft>>,
): BuildResult<ApprovalResponse> {
  const decisions: Record<string, ApprovalDecision> = {};
  const errors: Record<string, string> = {};
  for (const { action_id } of actions) {
    const draft = drafts[action_id];
    const decision = draft ? toApprovalDecision(draft) : i18n.t('approvals:errors.noDecision');
    if (typeof decision === 'string') errors[action_id] = decision;
    else decisions[action_id] = decision;
  }
  return Object.keys(errors).length > 0
    ? { ok: false, errors }
    : { ok: true, payload: { decisions } };
}

export function buildUncertainPayload(
  actions: readonly UncertainAction[],
  drafts: Partial<Record<string, UncertainDraft>>,
): BuildResult<UncertainResponse> {
  const decisions: Record<string, UncertainDecision> = {};
  const errors: Record<string, string> = {};
  for (const { action_id } of actions) {
    const draft = drafts[action_id];
    if (draft) decisions[action_id] = toUncertainDecision(draft);
    else errors[action_id] = i18n.t('approvals:errors.noDecision');
  }
  return Object.keys(errors).length > 0
    ? { ok: false, errors }
    : { ok: true, payload: { decisions } };
}
