import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/shared/api/axios-instance';
import { ruleKeys, ruleSavedSchema } from '@/entities/rule';

interface SaveRuleInput {
  filename: string;
  content: string;
}

export function useSaveRuleFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ filename, content }: SaveRuleInput) =>
      ruleSavedSchema.parse(
        (await api.put<unknown>(`/rules/${encodeURIComponent(filename)}`, { content })).data,
      ),
    onSuccess: async (saved) => {
      toast.success(`Rules saved — version ${saved.version_hash.slice(0, 8)}`);
      await queryClient.invalidateQueries({ queryKey: ruleKeys.all });
    },
  });
}
