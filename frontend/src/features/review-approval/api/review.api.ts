import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/shared/api/axios-instance';
import { threadKeys } from '@/entities/thread';
import type { ApprovalResponse, UncertainResponse } from '@/entities/approval';

type ReviewEndpoint = 'approvals' | 'uncertain';

interface ReviewCallbacks {
  /** Runs before the POST is sent, so the run is marked started first. */
  onSubmitting?: () => void;
  /** Runs when the POST fails, even after the review panel has unmounted. */
  onFailed?: () => void;
}

/** Both endpoints accept the decisions at once and resume the run (202). */
export function useSubmitReview(
  threadId: string,
  endpoint: ReviewEndpoint,
  { onSubmitting, onFailed }: ReviewCallbacks = {},
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: ApprovalResponse | UncertainResponse) => {
      await api.post(`/threads/${encodeURIComponent(threadId)}/${endpoint}`, payload);
    },
    // hook-level callbacks, unlike per-call ones, survive the form unmounting
    onMutate: () => {
      onSubmitting?.();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.detail(threadId) }),
    onError: (error) => {
      onFailed?.();
      toast.error(error.message);
    },
  });
}
