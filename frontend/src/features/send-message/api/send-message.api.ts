import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/shared/api/axios-instance';
import { threadKeys } from '@/entities/thread';
import { describeSendError } from '../model/send-error';

export function useSendMessage(threadId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (content: string) => {
      await api.post(`/threads/${encodeURIComponent(threadId)}/messages`, { content });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.detail(threadId) }),
    onError: (error) => {
      toast.error(describeSendError(error));
    },
  });
}
