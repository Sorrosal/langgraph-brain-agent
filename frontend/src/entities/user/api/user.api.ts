import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/axios-instance';
import type { User, UserProfile } from '../model/user.types';

const userKeys = {
  all: ['users'] as const,
  detail: (id: string) => ['users', id] as const,
  profile: () => ['users', 'profile'] as const,
};

async function fetchUsers(): Promise<User[]> {
  const { data } = await api.get<User[]>('/users');
  return data;
}

async function fetchUser(id: string): Promise<User> {
  const { data } = await api.get<User>(`/users/${id}`);
  return data;
}

async function fetchCurrentUserProfile(): Promise<UserProfile> {
  const { data } = await api.get<UserProfile>('/users/me');
  return data;
}

export function useUsers() {
  return useQuery({
    queryKey: userKeys.all,
    queryFn: fetchUsers,
  });
}

export function useUser(id: string) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => fetchUser(id),
    enabled: Boolean(id),
  });
}

export function useCurrentUserProfile() {
  return useQuery({
    queryKey: userKeys.profile(),
    queryFn: fetchCurrentUserProfile,
  });
}
