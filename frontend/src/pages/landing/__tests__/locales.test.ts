import { describe, expect, it } from 'vitest';
import enAuth from '@/shared/i18n/locales/en/auth.json';
import enLanding from '@/shared/i18n/locales/en/landing.json';
import esAuth from '@/shared/i18n/locales/es/auth.json';
import esLanding from '@/shared/i18n/locales/es/landing.json';

/** Dotted paths of every string leaf, with plural suffixes folded so `_one`/`_other` can differ. */
function leafKeys(node: unknown, prefix = ''): string[] {
  if (typeof node === 'string') return [prefix.replace(/_(one|other)$/, '')];
  return Object.entries(node as Record<string, unknown>).flatMap(([key, value]) =>
    leafKeys(value, prefix ? `${prefix}.${key}` : key),
  );
}

describe.each([
  ['auth', enAuth, esAuth],
  ['landing', enLanding, esLanding],
])('%s locale files', (_name, en, es) => {
  it('have the same keys in English and Spanish', () => {
    expect(new Set(leafKeys(es))).toEqual(new Set(leafKeys(en)));
  });
});
