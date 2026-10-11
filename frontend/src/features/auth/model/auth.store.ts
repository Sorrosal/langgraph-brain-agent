import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/entities/user';

interface AuthState {
  token: string | null;
  user: User | null;
  setToken: (token: string | null) => void;
  setUser: (user: User | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setToken: (token) => set({ token }),
      setUser: (user) => set({ user }),
      logout: () => {
        set({ token: null, user: null });
        window.location.href = '/login';
      },
    }),
    {
      name: 'auth-store',
      partialize: (state) => ({ token: state.token, user: state.user }),
    },
  ),
);

// Derived selector - not stored in state
export function selectIsAuthenticated(state: AuthState): boolean {
  return state.token !== null && state.user !== null;
}
