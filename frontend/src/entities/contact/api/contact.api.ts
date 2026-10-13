import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';
import { contactSchema } from '../model/contact.schemas';

export function useContacts(q: string) {
  return useQuery({
    queryKey: ['contacts', q] as const,
    queryFn: async () => {
      const { data } = await api.get<unknown>('/crm/contacts', { params: { q, limit: 100 } });
      return z.array(contactSchema).parse(data);
    },
    // keep rows on screen while a new search loads
    placeholderData: keepPreviousData,
  });
}
