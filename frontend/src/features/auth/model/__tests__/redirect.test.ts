import { describe, expect, it } from 'vitest';
import { redirectTarget } from '../redirect';

describe('redirectTarget', () => {
  it('returns the original app location with its query and hash', () => {
    const from = { pathname: '/app/inspector/t1', search: '?a=1', hash: '#x' };
    expect(redirectTarget({ from })).toBe('/app/inspector/t1?a=1#x');
  });

  it.each([
    ['no state', null],
    ['no from', {}],
    ['a string from', { from: '/app/brain' }],
    ['a path outside /app', { from: { pathname: '/login' } }],
    ['a look-alike prefix', { from: { pathname: '/application' } }],
    ['a protocol-relative path', { from: { pathname: '//evil.example/app' } }],
    ['an external url', { from: { pathname: 'https://evil.example/app/x' } }],
  ])('falls back to the chat for %s', (_label, state) => {
    expect(redirectTarget(state)).toBe('/app/chat');
  });
});
