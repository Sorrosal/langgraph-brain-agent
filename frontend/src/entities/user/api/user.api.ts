import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/axios-instance';
import { userSchema } from '../model/user.schemas';
import type { User } from '../model/user.types';

export const userKeys = {
  me: ['users', 'me'] as const,
};

async function fetchMe(): Promise<User> {
  const { data } = await api.get<unknown>('/auth/me');
  return userSchema.parse(data);
}

/** The signed-in user as the server sees it (also validates the stored token). */
export function useCurrentUser() {
  return useQuery({ queryKey: userKeys.me, queryFn: fetchMe });
}
