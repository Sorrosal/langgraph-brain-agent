import { afterEach, describe, expect, it } from 'vitest';
import { i18n } from '@/shared/i18n';
import { addMemorySchema } from '../memory-form.schemas';

function firstError(text: string) {
  const result = addMemorySchema.safeParse({ kind: 'fact', text });
  return result.success ? null : result.error.issues[0]?.message;
}

describe('addMemorySchema', () => {
  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('rejects blank and oversized text', () => {
    expect(firstError('   ')).toBe('Enter some text');
    expect(firstError('x'.repeat(2001))).toBe('At most 2000 characters');
    expect(firstError('Likes tea')).toBeNull();
  });

  it('reports errors in the active language', async () => {
    await i18n.changeLanguage('es');
    expect(firstError('')).toBe('Escribe algún texto');
  });
});
