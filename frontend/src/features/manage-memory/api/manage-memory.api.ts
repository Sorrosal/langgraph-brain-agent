import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/shared/api/axios-instance';
import { memoryKeys, memorySchema } from '@/entities/memory';
import type { AddMemoryValues } from '../model/memory-form.schemas';

export function useAddMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (values: AddMemoryValues) =>
      memorySchema.parse((await api.post<unknown>('/memories', values)).data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: memoryKeys.all }),
    onError: (error) => {
      toast.error(error.message);
    },
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/memories/${encodeURIComponent(id)}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: memoryKeys.all }),
    onError: (error) => {
      toast.error(error.message);
    },
  });
}
