import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/shared/api/axios-instance';
import { memorySchema, orgKnowledgeKeys } from '@/entities/memory';
import type { AddOrgKnowledgeValues } from '../model/org-knowledge-form.schemas';

export function useAddOrgKnowledge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (values: AddOrgKnowledgeValues) =>
      memorySchema.parse((await api.post<unknown>('/org-knowledge', values)).data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orgKnowledgeKeys.all }),
    onError: (error) => {
      toast.error(error.message);
    },
  });
}

export function useDeleteOrgKnowledge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/org-knowledge/${encodeURIComponent(id)}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orgKnowledgeKeys.all }),
    onError: (error) => {
      toast.error(error.message);
    },
  });
}
