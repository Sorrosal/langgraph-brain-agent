import { Navigate, Outlet } from 'react-router-dom';
import { selectIsAuthenticated, useAuthStore } from '@/features/auth';
import { useCurrentUser } from '@/entities/user';

export function AuthGuard() {
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  // Validates the stored token against the server; a 401 signs the user out (see api bridge).
  useCurrentUser();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
