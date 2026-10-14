import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/axios-instance';
import { z } from 'zod';
import { threadDetailSchema, threadSchema } from '../model/thread.schemas';
import type { Thread, ThreadDetail } from '../model/thread.types';

export const threadKeys = {
  all: ['threads'] as const,
  list: () => ['threads', 'list'] as const,
  detail: (id: string) => ['threads', 'detail', id] as const,
};

const LIST_LIMIT = 100;

async function fetchThreads(): Promise<Thread[]> {
  const { data } = await api.get<unknown>('/threads', { params: { limit: LIST_LIMIT } });
  return z.array(threadSchema).parse(data);
}

async function fetchThread(id: string): Promise<ThreadDetail> {
  const { data } = await api.get<unknown>(`/threads/${encodeURIComponent(id)}`);
  return threadDetailSchema.parse(data);
}

async function createThread(): Promise<Thread> {
  const { data } = await api.post<unknown>('/threads', { title: '' });
  return threadSchema.parse(data);
}

async function renameThread({ id, title }: { id: string; title: string }): Promise<Thread> {
  const { data } = await api.patch<unknown>(`/threads/${encodeURIComponent(id)}`, { title });
  return threadSchema.parse(data);
}

export function useThreads() {
  return useQuery({ queryKey: threadKeys.list(), queryFn: fetchThreads });
}

export function useThread(id: string | undefined) {
  return useQuery({
    queryKey: threadKeys.detail(id ?? ''),
    queryFn: () => fetchThread(id ?? ''),
    enabled: Boolean(id),
  });
}

export function useCreateThread() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createThread,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.list() }),
  });
}

export function useRenameThread() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: renameThread,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.all }),
  });
}

/** 409 `thread_busy` while a run is active: the caller explains it. */
export function useDeleteThread() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/threads/${encodeURIComponent(id)}`);
    },
    // Not awaited: the caller navigates away right after, before the list has refetched.
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: threadKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: threadKeys.list() });
    },
  });
}

/** Stops the active run; the thread stream then emits `run_failed` with code `run_cancelled`. */
export function useCancelRun(threadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.post(`/threads/${encodeURIComponent(threadId)}/cancel`);
    },
    // Also resyncs when nothing was running (409): the persisted status is the truth.
    onSettled: () => queryClient.invalidateQueries({ queryKey: threadKeys.detail(threadId) }),
  });
}

interface DismissCallbacks {
  /** Runs before the POST is sent, so the run is marked started first. */
  onSubmitting?: () => void;
  /** Runs when the POST fails, even after the calling component has unmounted. */
  onFailed?: (error: Error) => void;
  /** Runs once the server accepted it, before the thread queries are refreshed. */
  onDismissed?: () => void;
}

/**
 * Rejects every pending approval (or skips every uncertain action) and resumes the run so the
 * agent can acknowledge. Callbacks live on the hook so they survive the caller unmounting.
 */
export function useDismissRun(
  threadId: string,
  { onSubmitting, onFailed, onDismissed }: DismissCallbacks = {},
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.post(`/threads/${encodeURIComponent(threadId)}/dismiss`);
    },
    onMutate: () => {
      onSubmitting?.();
    },
    onSuccess: () => {
      onDismissed?.();
      return queryClient.invalidateQueries({ queryKey: threadKeys.all });
    },
    onError: (error) => {
      onFailed?.(error);
    },
  });
}
