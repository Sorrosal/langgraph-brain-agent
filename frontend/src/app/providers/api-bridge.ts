import { configureApi } from '@/shared/api/axios-instance';
import { queryClient } from '@/shared/api/query-client';
import { getValidToken, useAuthStore } from '@/features/auth';
import { router } from '@/app/router';

/** Connects the HTTP transport to the auth session and the router (soft redirect on 401). */
export function connectApiToSession(): void {
  configureApi({
    getToken: getValidToken,
    onUnauthorized: () => {
      useAuthStore.getState().clearSession();
      queryClient.clear();
      void router.navigate('/login', { replace: true });
    },
  });
}
