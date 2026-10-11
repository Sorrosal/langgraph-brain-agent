import { describe, expect, it } from 'vitest';
import { createRoutes } from '../index';

function collectPaths(routes: ReturnType<typeof createRoutes>): string[] {
  return routes.flatMap((route) => [
    ...(route.path ? [route.path] : []),
    ...collectPaths(route.children ?? []),
  ]);
}

describe('createRoutes', () => {
  it('has only the landing and the catch-all in landing-only mode', () => {
    expect(collectPaths(createRoutes(true))).toEqual(['/', '*']);
  });

  it('keeps the app routes in app mode', () => {
    const paths = collectPaths(createRoutes(false));
    expect(paths).toContain('/');
    expect(paths).toContain('/app/chat');
    expect(paths).toContain('/login');
  });
});
