import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/shared/api/axios-instance';
import { threadKeys } from '@/entities/thread';
import type { ApprovalResponse, UncertainResponse } from '@/entities/approval';

type ReviewEndpoint = 'approvals' | 'uncertain';

/** Both endpoints accept the decisions at once and resume the run (202). */
export function useSubmitReview(threadId: string, endpoint: ReviewEndpoint) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: ApprovalResponse | UncertainResponse) => {
      await api.post(`/threads/${encodeURIComponent(threadId)}/${endpoint}`, payload);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.detail(threadId) }),
    onError: (error) => {
      toast.error(error.message);
    },
  });
}
