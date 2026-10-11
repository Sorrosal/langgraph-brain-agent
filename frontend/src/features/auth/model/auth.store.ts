import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/entities/user';
import { persistedSessionSchema } from './auth.schemas';

interface Session {
  token: string | null;
  user: User | null;
  /** Epoch milliseconds at which the token stops being valid. */
  expiresAt: number | null;
}

interface AuthState extends Session {
  setSession: (session: { token: string; user: User; expiresIn: number }) => void;
  clearSession: () => void;
}

const EMPTY_SESSION: Session = { token: null, user: null, expiresAt: null };

export function isSessionValid(session: Session, now = Date.now()): boolean {
  return (
    session.token !== null &&
    session.user !== null &&
    session.expiresAt !== null &&
    session.expiresAt > now
  );
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      ...EMPTY_SESSION,
      setSession: ({ token, user, expiresIn }) => {
        set({ token, user, expiresAt: Date.now() + expiresIn * 1000 });
      },
      clearSession: () => {
        set(EMPTY_SESSION);
      },
    }),
    {
      name: 'auth-store',
      partialize: (state) => ({ token: state.token, user: state.user, expiresAt: state.expiresAt }),
      // An expired, malformed or old-format session counts as logged out.
      merge: (persisted, current) => {
        const parsed = persistedSessionSchema.safeParse(persisted);
        return parsed.success && parsed.data.expiresAt > Date.now()
          ? { ...current, ...parsed.data }
          : { ...current, ...EMPTY_SESSION };
      },
    },
  ),
);

// Derived selectors - not stored in state
export function selectIsAuthenticated(state: Session): boolean {
  return isSessionValid(state);
}

export function selectIsAdmin(state: Session): boolean {
  return isSessionValid(state) && state.user?.role === 'admin';
}

/** The bearer token while the session is alive, otherwise null (non-reactive). */
export function getValidToken(): string | null {
  const state = useAuthStore.getState();
  return isSessionValid(state) ? state.token : null;
}
