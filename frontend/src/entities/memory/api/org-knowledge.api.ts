import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';
import { memorySchema } from '../model/memory.schemas';

export const orgKnowledgeKeys = {
  all: ['org-knowledge'] as const,
};

/** Shared facts every user's agent can recall; same item shape as a memory. */
export function useOrgKnowledge() {
  return useQuery({
    queryKey: orgKnowledgeKeys.all,
    queryFn: async () => {
      const { data } = await api.get<unknown>('/org-knowledge');
      return z.array(memorySchema).parse(data);
    },
  });
}
