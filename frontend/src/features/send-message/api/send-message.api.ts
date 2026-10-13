import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/shared/api/axios-instance';
import { currentLanguage } from '@/shared/i18n';
import { threadKeys } from '@/entities/thread';
import { describeSendError } from '../model/send-error';

export function useSendMessage(threadId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (content: string) => {
      // Who and where: the agent resolves "tomorrow at 9" in the user's zone and language.
      await api.post(`/threads/${encodeURIComponent(threadId)}/messages`, {
        content,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        language: currentLanguage(),
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadKeys.detail(threadId) }),
    onError: (error) => {
      toast.error(describeSendError(error));
    },
  });
}
