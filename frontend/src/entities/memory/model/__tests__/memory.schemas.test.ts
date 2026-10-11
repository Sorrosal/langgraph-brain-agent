import { describe, expect, it } from 'vitest';
import { memorySchema } from '../memory.schemas';

const record = {
  id: 'm1',
  kind: 'preference',
  text: 'Prefers short answers',
  source_thread_id: null,
  created_at: '2026-01-01T00:00:00Z',
  score: null,
};

describe('memorySchema', () => {
  it('parses a listed memory and a search hit with a score', () => {
    expect(memorySchema.parse(record).score).toBeNull();
    expect(memorySchema.parse({ ...record, score: 0.82 }).score).toBe(0.82);
  });

  it('rejects an unknown kind', () => {
    expect(() => memorySchema.parse({ ...record, kind: 'rumour' })).toThrow();
  });
});
