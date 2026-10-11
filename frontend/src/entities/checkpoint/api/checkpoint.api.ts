import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';
import { checkpointSchema } from '../model/checkpoint.schemas';

export const checkpointKeys = {
  history: (threadId: string) => ['checkpoints', threadId] as const,
};

const HISTORY_LIMIT = 50;

export function useThreadHistory(threadId: string | undefined) {
  return useQuery({
    queryKey: checkpointKeys.history(threadId ?? ''),
    queryFn: async () => {
      const { data } = await api.get<unknown>(
        `/threads/${encodeURIComponent(threadId ?? '')}/history`,
        { params: { limit: HISTORY_LIMIT } },
      );
      return z.array(checkpointSchema).parse(data);
    },
    enabled: Boolean(threadId),
  });
}
