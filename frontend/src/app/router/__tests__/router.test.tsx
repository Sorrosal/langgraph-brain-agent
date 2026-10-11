import type { ReactElement } from 'react';
import { Navigate, type RouteObject } from 'react-router-dom';
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

describe('app routes', () => {
  function findRoute(
    routes: ReturnType<typeof createRoutes>,
    path: string,
  ): RouteObject | undefined {
    for (const route of routes) {
      if (route.path === path) return route;
      const found = findRoute(route.children ?? [], path);
      if (found) return found;
    }
    return undefined;
  }

  it('redirects /app to /app/chat', () => {
    const element = findRoute(createRoutes(false), '/app')?.element as ReactElement<{ to: string }>;
    expect(element.type).toBe(Navigate);
    expect(element.props.to).toBe('/app/chat');
  });

  it('shows a retryable error page when a route fails to load', () => {
    const [root] = createRoutes(false);
    expect(root?.errorElement).toBeDefined();
  });
});
