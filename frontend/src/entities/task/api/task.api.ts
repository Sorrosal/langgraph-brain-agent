import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';
import { taskSchema } from '../model/task.schemas';
import type { TaskStatus } from '../model/task.schemas';

export function useTasks(status: TaskStatus | '') {
  return useQuery({
    queryKey: ['tasks', status] as const,
    queryFn: async () => {
      const { data } = await api.get<unknown>('/tasks', {
        params: { limit: 100, ...(status && { status }) },
      });
      return z.array(taskSchema).parse(data);
    },
  });
}
