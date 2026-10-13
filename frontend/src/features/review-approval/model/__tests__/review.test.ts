import { describe, expect, it } from 'vitest';
import type { ActionRequest, UncertainAction } from '@/entities/approval';
import { i18n } from '@/shared/i18n';
import { argsError, buildApprovalPayload, buildUncertainPayload } from '../review';

function action(id: string): ActionRequest {
  return {
    action_id: id,
    tool_name: 'send_email',
    args: { to: 'a@b.co' },
    risk: 'high',
    reason: 'r',
  };
}

function uncertain(id: string): UncertainAction {
  return { action_id: id, tool_name: 'charge', args: {}, message: 'Outcome unknown' };
}

describe('buildApprovalPayload', () => {
  it('builds every decision type keyed by action id', () => {
    const result = buildApprovalPayload([action('a'), action('b'), action('c'), action('d')], {
      a: { type: 'approve' },
      b: { type: 'reject', reason: 'too risky' },
      c: { type: 'edit', argsText: '{"to": "x@y.z"}' },
      d: { type: 'respond', message: 'Already sent by phone' },
    });
    expect(result).toEqual({
      ok: true,
      payload: {
        decisions: {
          a: { type: 'approve' },
          b: { type: 'reject', reason: 'too risky' },
          c: { type: 'edit', args: { to: 'x@y.z' } },
          d: { type: 'respond', message: 'Already sent by phone' },
        },
      },
    });
  });

  it('omits a blank reject reason', () => {
    const result = buildApprovalPayload([action('a')], { a: { type: 'reject', reason: '  ' } });
    expect(result).toEqual({ ok: true, payload: { decisions: { a: { type: 'reject' } } } });
  });

  it('requires a decision for every action', () => {
    const result = buildApprovalPayload([action('a'), action('b')], { a: { type: 'approve' } });
    expect(result).toEqual({ ok: false, errors: { b: 'Choose a decision.' } });
  });

  it('rejects edited arguments that are not a JSON object', () => {
    const invalid = buildApprovalPayload([action('a')], { a: { type: 'edit', argsText: '{oops' } });
    expect(invalid).toEqual({ ok: false, errors: { a: 'Arguments must be valid JSON.' } });
    const array = buildApprovalPayload([action('a')], { a: { type: 'edit', argsText: '[1]' } });
    expect(array).toEqual({ ok: false, errors: { a: 'Arguments must be a JSON object.' } });
  });

  it('requires a message to respond with', () => {
    const result = buildApprovalPayload([action('a')], { a: { type: 'respond', message: ' ' } });
    expect(result).toEqual({ ok: false, errors: { a: 'Write the response to send back.' } });
  });
});

describe('argsError', () => {
  it('accepts a JSON object and reports anything else', () => {
    expect(argsError('{"a": 1}')).toBeUndefined();
    expect(argsError('{oops')).toBe('Arguments must be valid JSON.');
    expect(argsError('"text"')).toBe('Arguments must be a JSON object.');
  });

  it('follows the active language at call time', async () => {
    await i18n.changeLanguage('es');
    try {
      expect(argsError('{oops')).toBe('Los argumentos deben ser un JSON válido.');
      expect(buildApprovalPayload([action('a')], {})).toEqual({
        ok: false,
        errors: { a: 'Elige una decisión.' },
      });
    } finally {
      await i18n.changeLanguage('en');
    }
  });
});

describe('buildUncertainPayload', () => {
  it('builds confirm_done / retry / skip', () => {
    const result = buildUncertainPayload([uncertain('a'), uncertain('b'), uncertain('c')], {
      a: { type: 'confirm_done', message: 'Charged, ref 42' },
      b: { type: 'retry' },
      c: { type: 'skip' },
    });
    expect(result).toEqual({
      ok: true,
      payload: {
        decisions: {
          a: { type: 'confirm_done', message: 'Charged, ref 42' },
          b: { type: 'retry' },
          c: { type: 'skip' },
        },
      },
    });
  });

  it('omits a blank confirm message and requires every decision', () => {
    expect(
      buildUncertainPayload([uncertain('a')], { a: { type: 'confirm_done', message: '' } }),
    ).toEqual({ ok: true, payload: { decisions: { a: { type: 'confirm_done' } } } });
    expect(buildUncertainPayload([uncertain('a')], {})).toEqual({
      ok: false,
      errors: { a: 'Choose a decision.' },
    });
  });
});
