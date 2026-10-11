import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/axios-instance';
import { rulesSchema } from '../model/rule.schemas';

export const ruleKeys = { all: ['rules'] as const };

export function useRules() {
  return useQuery({
    queryKey: ruleKeys.all,
    queryFn: async () => rulesSchema.parse((await api.get<unknown>('/rules')).data),
  });
}
