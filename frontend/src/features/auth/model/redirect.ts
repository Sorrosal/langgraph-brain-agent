export const DEFAULT_REDIRECT = '/app/chat';

/**
 * Where to go after signing in: the location the AuthGuard bounced the user from
 * (`state: { from: location }`), but only same-app paths under `/app`; otherwise the chat.
 */
export function redirectTarget(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from;
  if (typeof from !== 'object' || from === null) return DEFAULT_REDIRECT;
  const { pathname, search, hash } = from as Record<string, unknown>;
  if (typeof pathname !== 'string' || !/^\/app(\/|$)/.test(pathname)) return DEFAULT_REDIRECT;
  return `${pathname}${typeof search === 'string' ? search : ''}${typeof hash === 'string' ? hash : ''}`;
}
