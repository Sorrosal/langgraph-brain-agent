import { z } from 'zod';
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

function parseArgs(text: string): { args: Record<string, unknown> } | { error: string } {
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    return { error: 'Arguments must be valid JSON.' };
  }
  const parsed = argsSchema.safeParse(json);
  return parsed.success ? { args: parsed.data } : { error: 'Arguments must be a JSON object.' };
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
        : 'Write the response to send back.';
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

const NO_DECISION = 'Choose a decision.';

/** One decision per action, keyed by action id; reports every problem at once. */
export function buildApprovalPayload(
  actions: readonly ActionRequest[],
  drafts: Partial<Record<string, ApprovalDraft>>,
): BuildResult<ApprovalResponse> {
  const decisions: Record<string, ApprovalDecision> = {};
  const errors: Record<string, string> = {};
  for (const { action_id } of actions) {
    const draft = drafts[action_id];
    const decision = draft ? toApprovalDecision(draft) : NO_DECISION;
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
    else errors[action_id] = NO_DECISION;
  }
  return Object.keys(errors).length > 0
    ? { ok: false, errors }
    : { ok: true, payload: { decisions } };
}
