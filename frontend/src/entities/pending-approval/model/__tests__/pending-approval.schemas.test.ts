import { describe, expect, it } from 'vitest';
import { pendingApprovalSchema } from '../pending-approval.schemas';

const base = { thread_id: 't1', title: 'Report', updated_at: '2026-01-01T00:00:00Z' };

describe('pendingApprovalSchema', () => {
  it('parses an approval interrupt as the backend sends it', () => {
    const parsed = pendingApprovalSchema.parse({
      ...base,
      interrupt: {
        kind: 'approval_required',
        actions: [
          { action_id: 'c1', tool_name: 'send_email', args: {}, risk: 'high', reason: 'Sends' },
        ],
      },
    });
    expect(parsed.interrupt.actions).toHaveLength(1);
  });

  it('parses an uncertain-execution interrupt', () => {
    const parsed = pendingApprovalSchema.parse({
      ...base,
      interrupt: {
        kind: 'uncertain_execution',
        actions: [{ action_id: 'u1', tool_name: 'charge', args: {}, message: 'Timed out' }],
      },
    });
    expect(parsed.interrupt.kind).toBe('uncertain_execution');
  });

  it('rejects an unknown interrupt kind', () => {
    expect(() =>
      pendingApprovalSchema.parse({ ...base, interrupt: { kind: 'other', actions: [] } }),
    ).toThrow();
  });
});
