import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';
import { pendingApprovalSchema } from '../model/pending-approval.schemas';

export const pendingApprovalKeys = { all: ['pending-approvals'] as const };

const REFRESH_MS = 15_000;

export function usePendingApprovals() {
  return useQuery({
    queryKey: pendingApprovalKeys.all,
    queryFn: async () => {
      const { data } = await api.get<unknown>('/approvals/pending');
      return z.array(pendingApprovalSchema).parse(data);
    },
    refetchInterval: REFRESH_MS,
    refetchOnWindowFocus: true,
  });
}
