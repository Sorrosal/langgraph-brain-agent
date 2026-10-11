import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/axios-instance';
import { tokenResponseSchema } from '../model/auth.schemas';
import type { LoginFormValues, RegisterFormValues } from '../model/auth.schemas';
import { useAuthStore } from '../model/auth.store';

async function loginRequest(credentials: LoginFormValues) {
  const { data } = await api.post<unknown>('/auth/login', credentials);
  return tokenResponseSchema.parse(data);
}

/** Registration answers 202 without a token (no account enumeration), so sign in afterwards. */
async function registerRequest(values: RegisterFormValues) {
  const { display_name, email, password } = values;
  await api.post('/auth/register', { display_name, email, password });
  return loginRequest({ email, password });
}

function useSessionMutation<TValues>(
  request: (values: TValues) => ReturnType<typeof loginRequest>,
) {
  const setSession = useAuthStore((state) => state.setSession);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: request,
    onSuccess: (data) => {
      queryClient.clear();
      setSession({ token: data.access_token, user: data.user, expiresIn: data.expires_in });
    },
  });
}

export function useLogin() {
  return useSessionMutation(loginRequest);
}

export function useRegister() {
  return useSessionMutation(registerRequest);
}

/** There is no server-side session to end: signing out drops the token and cached data. */
export function useLogout() {
  const clearSession = useAuthStore((state) => state.clearSession);
  const queryClient = useQueryClient();

  return function logout() {
    clearSession();
    queryClient.clear();
  };
}
