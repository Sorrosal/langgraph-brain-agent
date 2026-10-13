import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useReducer } from 'react';
import { getAccessToken } from '@/shared/api/axios-instance';
import { env } from '@/shared/config/env';
import { threadKeys } from '@/entities/thread';
import {
  initialStreamState,
  parseStreamEvent,
  STREAM_EVENT_TYPES,
  streamReducer,
} from '../model/stream.reducer';

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30_000;
const REFRESH_ON = new Set(['interrupt', 'run_completed', 'run_failed']);

function streamUrl(threadId: string, token: string, after: number | null): string {
  const params = new URLSearchParams({ access_token: token });
  if (after !== null) params.set('after', String(after));
  return `${env.VITE_API_URL}/threads/${encodeURIComponent(threadId)}/events?${params.toString()}`;
}

function parseJson(text: unknown): unknown {
  if (typeof text !== 'string') return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

/**
 * Live run of a thread over SSE. Reconnects with exponential backoff, resuming after the last
 * event id seen (`?after=`); replayed events are ignored by the reducer. Remount (e.g. with a
 * `key`) per thread to start from a clean state.
 */
export function useThreadStream(threadId: string | undefined) {
  const queryClient = useQueryClient();
  const [state, dispatch] = useReducer(streamReducer, initialStreamState);
  const settle = useCallback(() => {
    dispatch({ type: 'settle' });
  }, []);

  useEffect(() => {
    if (!threadId) return;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let lastId: number | null = null;
    let attempt = 0;
    let reconnected = false;
    let disposed = false;

    function refresh() {
      void queryClient.invalidateQueries({ queryKey: threadKeys.all });
    }

    function connect() {
      const token = getAccessToken();
      if (disposed || !token || !threadId) return;
      const current = new EventSource(streamUrl(threadId, token, lastId));
      source = current;

      current.onopen = () => {
        attempt = 0;
        // Events may have been missed while disconnected: resync the persisted state.
        if (reconnected) refresh();
      };
      current.onerror = () => {
        current.close();
        reconnected = true;
        timer = setTimeout(connect, Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS));
        attempt += 1;
      };
      for (const type of STREAM_EVENT_TYPES) {
        current.addEventListener(type, (message) => {
          const id = Number(message.lastEventId);
          if (!Number.isFinite(id)) return;
          const event = parseStreamEvent(id, type, parseJson(message.data));
          if (!event) return;
          lastId = Math.max(lastId ?? 0, id);
          dispatch({ type: 'event', event });
          if (REFRESH_ON.has(type)) refresh();
        });
      }
    }

    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      source?.close();
    };
  }, [threadId, queryClient]);

  return {
    state,
    markRunStarted: () => {
      dispatch({ type: 'run_started', cursor: state.lastEventId });
    },
    markRunStartFailed: () => {
      dispatch({ type: 'run_start_failed' });
    },
    settle,
  };
}
