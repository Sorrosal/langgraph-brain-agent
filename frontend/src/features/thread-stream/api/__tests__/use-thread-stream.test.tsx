import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';
import { configureApi } from '@/shared/api/axios-instance';
import { useThreadStream } from '../use-thread-stream';

type Listener = (event: MessageEvent<string>) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly listeners = new Map<string, Listener[]>();
  closed = false;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;

  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.closed = true;
  }

  open() {
    this.onopen?.();
  }

  fail() {
    this.onerror?.();
  }

  emit(id: number, type: string, data: unknown) {
    const event = new MessageEvent(type, { data: JSON.stringify(data), lastEventId: String(id) });
    this.listeners.get(type)?.forEach((listener) => {
      listener(event);
    });
  }
}

function latest(): FakeEventSource {
  const source = FakeEventSource.instances.at(-1);
  if (!source) throw new Error('no EventSource was created');
  return source;
}

function connected(): number {
  return FakeEventSource.instances.length;
}

describe('useThreadStream', () => {
  let queryClient: QueryClient;
  let invalidate: MockInstance<QueryClient['invalidateQueries']>;

  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  function mount(threadId: string | undefined) {
    return renderHook(() => useThreadStream(threadId), { wrapper: Wrapper });
  }

  beforeEach(() => {
    vi.useFakeTimers();
    FakeEventSource.instances = [];
    vi.stubGlobal('EventSource', FakeEventSource);
    configureApi({ getToken: () => 'tok', onUnauthorized: () => undefined });
    queryClient = new QueryClient();
    invalidate = vi.spyOn(queryClient, 'invalidateQueries');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('connects with the access token and no cursor first', () => {
    mount('t1');
    const url = new URL(latest().url);
    expect(url.pathname).toBe('/threads/t1/events');
    expect(url.searchParams.get('access_token')).toBe('tok');
    expect(url.searchParams.has('after')).toBe(false);
  });

  it('does not connect without a thread or a token', () => {
    mount(undefined);
    configureApi({ getToken: () => null, onUnauthorized: () => undefined });
    mount('t1');
    expect(connected()).toBe(0);
  });

  it('feeds events into the state and invalidates thread queries on run end', () => {
    const { result } = mount('t1');
    act(() => {
      latest().emit(1, 'token', { text: 'Hi' });
    });
    expect(result.current.state).toMatchObject({ runStatus: 'running', streamingText: 'Hi' });
    expect(invalidate).not.toHaveBeenCalled();

    act(() => {
      latest().emit(2, 'run_completed', { status: 'completed' });
    });
    expect(result.current.state.runStatus).toBe('idle');
    expect(invalidate).toHaveBeenCalled();
  });

  it('invalidates on interrupt and run_failed too', () => {
    mount('t1');
    act(() => {
      latest().emit(1, 'interrupt', { kind: 'approval_required', actions: [] });
    });
    expect(invalidate).toHaveBeenCalledTimes(1);
    act(() => {
      latest().emit(2, 'run_failed', { code: 'run_failed', message: 'x' });
    });
    expect(invalidate).toHaveBeenCalledTimes(2);
  });

  it('reconnects with backoff and resumes after the last event id, deduping the replay', () => {
    const { result } = mount('t1');
    const first = latest();
    act(() => {
      first.emit(100, 'token', { text: 'a' });
      first.emit(101, 'token', { text: 'b' });
      first.fail();
    });
    expect(first.closed).toBe(true);
    expect(connected()).toBe(1);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    const second = latest();
    expect(second).not.toBe(first);
    expect(new URL(second.url).searchParams.get('after')).toBe('101');

    act(() => {
      second.open();
      second.emit(101, 'token', { text: 'b' });
      second.emit(102, 'token', { text: 'c' });
    });
    expect(result.current.state.streamingText).toBe('abc');
    // a reconnect may have missed events beyond the server buffer: resync the persisted state
    expect(invalidate).toHaveBeenCalled();
  });

  it('backs off exponentially until a connection opens', () => {
    mount('t1');
    act(() => {
      latest().fail();
      vi.advanceTimersByTime(999);
    });
    expect(connected()).toBe(1);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(connected()).toBe(2);

    act(() => {
      latest().fail();
      vi.advanceTimersByTime(1999);
    });
    expect(connected()).toBe(2);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(connected()).toBe(3);

    act(() => {
      latest().open();
      latest().fail();
      vi.advanceTimersByTime(1000);
    });
    expect(connected()).toBe(4);
  });

  it('closes the source and cancels pending reconnects on unmount', () => {
    const { unmount } = mount('t1');
    const source = latest();
    act(() => {
      source.fail();
    });
    unmount();
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(connected()).toBe(1);
    expect(source.closed).toBe(true);
  });

  it('markRunStarted switches to running', () => {
    const { result } = mount('t1');
    act(() => {
      result.current.markRunStarted();
    });
    expect(result.current.state.runStatus).toBe('running');
  });
});
