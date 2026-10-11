import { describe, expect, it } from 'vitest';
import { ruleSavedSchema, rulesSchema } from '../rule.schemas';

describe('rule schemas', () => {
  it('parses the rules payload; rule fields the YAML omitted get defaults', () => {
    const parsed = rulesSchema.parse({
      version_hash: 'abc123',
      persona: null,
      guidelines: [{ id: 'g1', text: 'Be concise' }],
      hard_rules: [
        {
          id: 'no-wire',
          description: 'Wires need approval',
          when: { tool: 'send_wire', args: { amount: { gt: 100 } } },
          action: 'require_approval',
        },
      ],
      files: [{ name: 'base.yaml', content: 'persona: x' }],
    });
    expect(parsed.guidelines[0]?.priority).toBe(0);
    expect(parsed.hard_rules[0]?.risk).toBe('high');
    expect(parsed.hard_rules[0]?.when.tool).toBe('send_wire');
  });

  it('parses the save response', () => {
    expect(ruleSavedSchema.parse({ filename: 'base.yaml', version_hash: 'f00' }).version_hash).toBe(
      'f00',
    );
  });
});
