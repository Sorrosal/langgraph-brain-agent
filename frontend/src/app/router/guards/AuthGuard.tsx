import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { selectIsAuthenticated, useAuthStore } from '@/features/auth';
import { useCurrentUser } from '@/entities/user';

export function AuthGuard() {
  const isAuthenticated = useAuthStore(selectIsAuthenticated);
  const location = useLocation();
  // Validates the stored token against the server; a 401 signs the user out (see api bridge).
  // Only with a session: right after sign-out it would just earn a noisy 401.
  useCurrentUser(isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
