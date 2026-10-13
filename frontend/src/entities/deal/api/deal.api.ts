import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';
import { dealSchema } from '../model/deal.schemas';
import type { DealStage } from '../model/deal.schemas';

export function useDeals(stage: DealStage | '') {
  return useQuery({
    queryKey: ['deals', stage] as const,
    queryFn: async () => {
      const { data } = await api.get<unknown>('/crm/deals', {
        params: { limit: 100, ...(stage && { stage }) },
      });
      return z.array(dealSchema).parse(data);
    },
    placeholderData: keepPreviousData,
  });
}
