import { describe, expect, it } from 'vitest';
import { checkpointSchema } from '../checkpoint.schemas';

describe('checkpointSchema', () => {
  it('parses a checkpoint, including a missing timestamp and an empty next', () => {
    const parsed = checkpointSchema.parse({
      checkpoint_id: '1f0a-bc',
      step: 3,
      created_at: null,
      source: 'loop',
      writes: ['agent'],
      next: [],
      message_count: 4,
    });
    expect(parsed.created_at).toBeNull();
    expect(parsed.next).toEqual([]);
  });
});
