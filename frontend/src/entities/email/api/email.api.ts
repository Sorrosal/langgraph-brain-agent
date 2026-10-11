import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';
import { emailSchema } from '../model/email.schemas';
import type { EmailFolder } from '../model/email.schemas';

export function useEmails(folder: EmailFolder, q: string) {
  return useQuery({
    queryKey: ['emails', folder, q] as const,
    queryFn: async () => {
      const { data } = await api.get<unknown>('/emails', { params: { folder, q, limit: 100 } });
      return z.array(emailSchema).parse(data);
    },
  });
}
