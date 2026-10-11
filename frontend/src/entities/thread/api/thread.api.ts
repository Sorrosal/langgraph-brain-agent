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
