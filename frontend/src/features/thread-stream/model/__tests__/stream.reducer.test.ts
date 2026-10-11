import { describe, expect, it } from 'vitest';
import { initialStreamState, parseStreamEvent, streamReducer } from '../stream.reducer';
import type { StreamAction, StreamEvent, StreamState } from '../stream.reducer';

function ev(id: number, type: string, data: unknown): StreamAction {
  const event = parseStreamEvent(id, type, data);
  if (!event) throw new Error(`invalid test event ${type}`);
  return { type: 'event', event };
}

function run(actions: StreamAction[], from: StreamState = initialStreamState): StreamState {
  return actions.reduce(streamReducer, from);
}

const approval = {
  kind: 'approval_required',
  actions: [
    {
      action_id: 'c1',
      tool_name: 'send_email',
      args: { to: 'a@b.co' },
      risk: 'high',
      reason: 'Sends email',
    },
  ],
} as const;

describe('parseStreamEvent', () => {
  it('rejects unknown types and malformed payloads', () => {
    expect(parseStreamEvent(1, 'mystery', {})).toBeNull();
    expect(parseStreamEvent(1, 'token', { text: 42 })).toBeNull();
    expect(parseStreamEvent(1, 'interrupt', { kind: 'nope' })).toBeNull();
  });

  it('accepts every event of the backend contract', () => {
    const cases: [string, unknown][] = [
      ['token', { text: 'hi' }],
      ['node', { node: 'reason' }],
      ['tool_call', { id: 'c1', name: 'search', args: {} }],
      ['tool_result', { id: 'c1', name: 'search', status: 'success', content: 'ok' }],
      ['interrupt', approval],
      ['run_completed', { status: 'completed' }],
      ['run_failed', { code: 'run_failed', message: 'The run failed.' }],
    ];
    for (const [type, data] of cases) {
      const event: StreamEvent | null = parseStreamEvent(5, type, data);
      expect(event?.type).toBe(type);
    }
  });
});

describe('streamReducer', () => {
  it('starts unknown (null status) so thread detail can speak first', () => {
    expect(initialStreamState.runStatus).toBeNull();
  });

  it('accumulates tokens while running', () => {
    const state = run([ev(1, 'token', { text: 'Hel' }), ev(2, 'token', { text: 'lo' })]);
    expect(state).toMatchObject({ runStatus: 'running', streamingText: 'Hello', lastEventId: 2 });
  });

  it('follows a full tool-using run', () => {
    let state = run([
      ev(1, 'node', { node: 'load_context' }),
      ev(2, 'tool_call', { id: 'c1', name: 'search', args: { q: 'x' } }),
      ev(3, 'node', { node: 'reason' }),
    ]);
    expect(state.activeNode).toBe('reason');
    expect(state.toolActivity).toEqual([
      { id: 'c1', name: 'search', args: { q: 'x' }, status: 'running' },
    ]);

    state = run(
      [ev(4, 'tool_result', { id: 'c1', name: 'search', status: 'success', content: 'r' })],
      state,
    );
    expect(state.toolActivity[0]).toMatchObject({ status: 'success', content: 'r' });

    state = run(
      [ev(5, 'token', { text: 'Done' }), ev(6, 'run_completed', { status: 'completed' })],
      state,
    );
    expect(state).toMatchObject({
      runStatus: 'idle',
      streamingText: '',
      activeNode: null,
      toolActivity: [],
      pendingInterrupt: null,
      lastEventId: 6,
    });
  });

  it('starts a fresh text segment after the reason node closes one', () => {
    const state = run([
      ev(1, 'token', { text: 'first' }),
      ev(2, 'node', { node: 'reason' }),
      ev(3, 'token', { text: 'second' }),
    ]);
    expect(state.streamingText).toBe('second');
  });

  it('marks tool results with status error', () => {
    const state = run([
      ev(1, 'tool_call', { id: 'c1', name: 'x', args: {} }),
      ev(2, 'tool_result', { id: 'c1', name: 'x', status: 'error', content: 'boom' }),
    ]);
    expect(state.toolActivity[0]?.status).toBe('error');
  });

  it('keeps the pending interrupt when the run pauses for approval', () => {
    const state = run([
      ev(1, 'interrupt', approval),
      ev(2, 'run_completed', { status: 'interrupted' }),
    ]);
    expect(state.runStatus).toBe('interrupted');
    expect(state.pendingInterrupt).toEqual(approval);
  });

  it('records a failed run and clears live state', () => {
    const state = run([
      ev(1, 'token', { text: 'x' }),
      ev(2, 'run_failed', { code: 'lease_lost', message: 'Taken over.' }),
    ]);
    expect(state).toMatchObject({
      runStatus: 'failed',
      streamingText: '',
      error: { code: 'lease_lost', message: 'Taken over.' },
    });
  });

  it('ignores replayed events (dedupe by id) after a reconnect', () => {
    const first = run([ev(10, 'token', { text: 'a' }), ev(11, 'token', { text: 'b' })]);
    const replayed = run(
      [
        ev(10, 'token', { text: 'a' }),
        ev(11, 'token', { text: 'b' }),
        ev(12, 'token', { text: 'c' }),
      ],
      first,
    );
    expect(replayed.streamingText).toBe('abc');
    expect(replayed.lastEventId).toBe(12);
    expect(streamReducer(first, ev(11, 'token', { text: 'b' }))).toBe(first);
  });

  it('run_started resets live state but keeps the dedupe cursor', () => {
    const failed = run([ev(7, 'run_failed', { code: 'run_failed', message: 'x' })]);
    const state = streamReducer(failed, { type: 'run_started' });
    expect(state).toMatchObject({ runStatus: 'running', error: null, lastEventId: 7 });
  });

  it('reset returns to the initial state', () => {
    expect(streamReducer(run([ev(3, 'token', { text: 'a' })]), { type: 'reset' })).toEqual(
      initialStreamState,
    );
  });
});
