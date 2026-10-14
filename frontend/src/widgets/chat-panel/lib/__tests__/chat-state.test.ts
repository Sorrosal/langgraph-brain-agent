import { describe, expect, it } from 'vitest';
import type { ThreadDetail } from '@/entities/thread';
import type { StreamState } from '@/features/thread-stream';
import { deriveChatView } from '../chat-state';

const pending: ThreadDetail['pending_interrupt'] = {
  kind: 'approval_required',
  actions: [],
};

function detail(overrides: Partial<ThreadDetail> = {}): ThreadDetail {
  return {
    id: 't1',
    title: '',
    created_at: '',
    updated_at: '',
    messages: [],
    summary: null,
    pending_interrupt: null,
    run: { status: 'idle' },
    approvals: [],
    ...overrides,
  };
}

function stream(overrides: Partial<StreamState> = {}): StreamState {
  return {
    lastEventId: 0,
    runStatus: null,
    streamingText: '',
    textSealed: false,
    activeNode: null,
    toolActivity: [],
    pendingInterrupt: null,
    error: null,
    settled: false,
    ...overrides,
  };
}

describe('deriveChatView', () => {
  it('falls back to the persisted run before the stream has spoken', () => {
    const view = deriveChatView(
      detail({ run: { status: 'interrupted' }, pending_interrupt: pending }),
      stream(),
    );
    expect(view).toMatchObject({ status: 'interrupted', pendingInterrupt: pending, busy: true });
    expect(view.activity).toEqual({ kind: 'approval' });
  });

  it('lets the stream override a stale detail (run finished, refetch pending)', () => {
    const view = deriveChatView(
      detail({ run: { status: 'running' } }),
      stream({ runStatus: 'idle' }),
    );
    expect(view).toMatchObject({ status: 'idle', busy: false, activity: null });
  });

  it('names the running tool, otherwise says Thinking', () => {
    const running = stream({
      runStatus: 'running',
      toolActivity: [{ id: 'c1', name: 'search', status: 'running' }],
    });
    expect(deriveChatView(detail(), running).activity).toEqual({ kind: 'tool', name: 'search' });
    expect(deriveChatView(detail(), stream({ runStatus: 'running' })).activity).toEqual({
      kind: 'thinking',
    });
  });

  it('hides the approval panel once a resumed run is running', () => {
    const view = deriveChatView(
      detail({ run: { status: 'interrupted' }, pending_interrupt: pending }),
      stream({ runStatus: 'running' }),
    );
    expect(view.pendingInterrupt).toBeNull();
  });

  it('reports failures', () => {
    const view = deriveChatView(
      detail(),
      stream({ runStatus: 'failed', error: { code: 'run_failed', message: 'The run failed.' } }),
    );
    expect(view).toMatchObject({ failure: 'The run failed.', cancelled: false, busy: false });
  });

  it('treats a stopped run as a neutral notice, not a failure', () => {
    const view = deriveChatView(
      detail(),
      stream({
        runStatus: 'failed',
        error: { code: 'run_cancelled', message: 'The run was cancelled.' },
      }),
    );
    expect(view).toMatchObject({ failure: null, cancelled: true, busy: false });
  });

  it('stops being cancelled once a new run starts', () => {
    const view = deriveChatView(
      detail(),
      stream({
        runStatus: 'running',
        error: { code: 'run_cancelled', message: 'The run was cancelled.' },
      }),
    );
    expect(view).toMatchObject({ failure: null, cancelled: false, busy: true });
  });
});

describe('deriveChatView failures without a message', () => {
  it('flags a persisted failure so the panel shows the generic text', () => {
    const view = deriveChatView(detail({ run: { status: 'failed' } }), stream());
    expect(view.failure).toBe(true);
  });
});

describe('deriveChatView after a reload', () => {
  it('shows a stopped run as stopped, not as a failure', () => {
    const view = deriveChatView(
      detail({ run: { status: 'failed', error: 'The run was cancelled.', code: 'run_cancelled' } }),
      stream(),
    );
    expect(view).toMatchObject({ cancelled: true, failure: null });
  });
});
