import { useMutation } from '@tanstack/react-query';
import { api } from '@/shared/api/axios-instance';
import { queryClient } from '@/shared/api/query-client';
import type { User } from '@/entities/user';
import { useAuthStore } from '../model/auth.store';
import type { LoginFormValues, RegisterFormValues } from '../model/auth.schemas';

interface AuthResponse {
  token: string;
  refreshToken: string;
  user: User;
}

async function loginRequest(credentials: LoginFormValues): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>('/auth/login', credentials);
  return data;
}

async function registerRequest(
  payload: Omit<RegisterFormValues, 'confirmPassword'>,
): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>('/auth/register', payload);
  return data;
}

async function logoutRequest(): Promise<void> {
  await api.post('/auth/logout');
}

export function useLogin() {
  const { setToken, setUser } = useAuthStore();

  return useMutation({
    mutationFn: loginRequest,
    onSuccess: (data) => {
      setToken(data.token);
      setUser(data.user);
      if (data.refreshToken) {
        localStorage.setItem('refresh-token', data.refreshToken);
      }
      void queryClient.invalidateQueries();
    },
  });
}

export function useRegister() {
  const { setToken, setUser } = useAuthStore();

  return useMutation({
    mutationFn: (values: RegisterFormValues) => {
      const { confirmPassword: _confirmPassword, ...rest } = values;
      return registerRequest(rest);
    },
    onSuccess: (data) => {
      setToken(data.token);
      setUser(data.user);
      if (data.refreshToken) {
        localStorage.setItem('refresh-token', data.refreshToken);
      }
    },
  });
}

export function useLogout() {
  const { logout } = useAuthStore();

  return useMutation({
    mutationFn: logoutRequest,
    onSettled: () => {
      queryClient.clear();
      localStorage.removeItem('refresh-token');
      logout();
    },
  });
}
