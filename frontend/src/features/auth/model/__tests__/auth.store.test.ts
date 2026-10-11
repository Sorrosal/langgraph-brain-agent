import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { User } from '@/entities/user';
import { getValidToken, selectIsAuthenticated, useAuthStore } from '../auth.store';

const user: User = {
  id: 'u1',
  email: 'a@b.co',
  display_name: 'Ada',
  role: 'operator',
  created_at: '2026-01-01T00:00:00Z',
};

function persist(state: Record<string, unknown>) {
  localStorage.setItem('auth-store', JSON.stringify({ state, version: 0 }));
}

describe('auth store', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-01T12:00:00Z'));
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('is authenticated after a session is set, until expires_in elapses', () => {
    useAuthStore.getState().setSession({ token: 't', user, expiresIn: 60 });
    expect(selectIsAuthenticated(useAuthStore.getState())).toBe(true);
    expect(getValidToken()).toBe('t');

    vi.advanceTimersByTime(59_000);
    expect(getValidToken()).toBe('t');

    vi.advanceTimersByTime(2_000);
    expect(selectIsAuthenticated(useAuthStore.getState())).toBe(false);
    expect(getValidToken()).toBeNull();
  });

  it('clears the session', () => {
    useAuthStore.getState().setSession({ token: 't', user, expiresIn: 60 });
    useAuthStore.getState().clearSession();
    expect(useAuthStore.getState()).toMatchObject({ token: null, user: null, expiresAt: null });
  });

  it('restores a live persisted session on rehydrate', async () => {
    persist({ token: 't', user, expiresAt: Date.now() + 60_000 });
    await useAuthStore.persist.rehydrate();
    expect(selectIsAuthenticated(useAuthStore.getState())).toBe(true);
  });

  it('treats an expired persisted session as logged out', async () => {
    persist({ token: 't', user, expiresAt: Date.now() - 1 });
    await useAuthStore.persist.rehydrate();
    expect(selectIsAuthenticated(useAuthStore.getState())).toBe(false);
    expect(useAuthStore.getState().token).toBeNull();
  });

  it('drops persisted state without an expiry (old format)', async () => {
    persist({ token: 't', user });
    await useAuthStore.persist.rehydrate();
    expect(useAuthStore.getState().token).toBeNull();
  });
});
