import { describe, expect, it } from 'vitest';
import { findNavItem } from '../nav-items';

describe('findNavItem', () => {
  it('matches a section and its nested routes', () => {
    expect(findNavItem('/app/chat')?.key).toBe('chat');
    expect(findNavItem('/app/chat/abc-123')?.key).toBe('chat');
    expect(findNavItem('/app/inspector/t1')?.key).toBe('inspector');
  });

  it('does not match a path that merely shares a prefix', () => {
    expect(findNavItem('/app/chatty')).toBeUndefined();
    expect(findNavItem('/app/unknown')).toBeUndefined();
  });
});
