import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';
import { memorySchema } from '../model/memory.schemas';
import type { MemoryKind } from '../model/memory.schemas';

export const memoryKeys = {
  all: ['memories'] as const,
  list: (kind: MemoryKind | null) => ['memories', 'list', kind] as const,
  search: (q: string) => ['memories', 'search', q] as const,
};

const memoriesSchema = z.array(memorySchema);

export function useMemories(kind: MemoryKind | null) {
  return useQuery({
    queryKey: memoryKeys.list(kind),
    queryFn: async () => {
      const { data } = await api.get<unknown>('/memories', {
        params: kind ? { kind } : undefined,
      });
      return memoriesSchema.parse(data);
    },
    // keep the list on screen while another kind loads
    placeholderData: keepPreviousData,
  });
}

/** Semantic search; disabled for a blank query (the backend rejects it). */
export function useMemorySearch(q: string) {
  return useQuery({
    queryKey: memoryKeys.search(q),
    queryFn: async () => {
      const { data } = await api.get<unknown>('/memories/search', { params: { q } });
      return memoriesSchema.parse(data);
    },
    enabled: q.trim().length > 0,
    placeholderData: keepPreviousData,
  });
}
