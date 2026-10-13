import { describe, expect, it } from 'vitest';
import enBrain from '@/shared/i18n/locales/en/brain.json';
import enData from '@/shared/i18n/locales/en/data.json';
import esBrain from '@/shared/i18n/locales/es/brain.json';
import esData from '@/shared/i18n/locales/es/data.json';

function keys(node: unknown, prefix = ''): string[] {
  if (typeof node !== 'object' || node === null) return [prefix];
  return Object.entries(node).flatMap(([key, value]) =>
    keys(value, prefix ? `${prefix}.${key}` : key),
  );
}

describe.each([
  ['brain', enBrain, esBrain],
  ['data', enData, esData],
])('%s locale', (_namespace, en, es) => {
  it('has the same keys in English and Spanish', () => {
    expect(keys(es).sort()).toEqual(keys(en).sort());
  });

  it('keeps interpolation variables in every translation', () => {
    const variables = (text: string) => text.match(/{{\w+}}/g)?.sort() ?? [];
    const flat = (node: unknown): Record<string, string> =>
      Object.fromEntries(
        keys(node).map((path) => [
          path,
          path
            .split('.')
            .reduce<unknown>(
              (value, key) => (value as Record<string, unknown>)[key],
              node,
            ) as string,
        ]),
      );
    const enFlat = flat(en);
    const esFlat = flat(es);
    for (const [path, text] of Object.entries(enFlat)) {
      expect(variables(esFlat[path] ?? ''), path).toEqual(variables(text));
    }
  });
});
