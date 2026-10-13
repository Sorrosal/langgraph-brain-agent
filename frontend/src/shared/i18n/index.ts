import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

export const LANGUAGES = ['en', 'es'] as const;
export type Language = (typeof LANGUAGES)[number];

const STORAGE_KEY = 'lng';
const FALLBACK: Language = 'en';

/** One JSON file per namespace and language: `locales/<lng>/<namespace>.json`. */
const files = import.meta.glob<Record<string, unknown>>('./locales/*/*.json', {
  eager: true,
  import: 'default',
});

const resources: Record<string, Record<string, Record<string, unknown>>> = {};
for (const [path, bundle] of Object.entries(files)) {
  const match = /\.\/locales\/(\w+)\/([\w-]+)\.json$/.exec(path);
  if (!match) continue;
  const [, lng = FALLBACK, ns = 'common'] = match;
  (resources[lng] ??= {})[ns] = bundle;
}

function isLanguage(value: string | null | undefined): value is Language {
  return (LANGUAGES as readonly string[]).includes(value ?? '');
}

function detectLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLanguage(saved)) return saved;
  } catch {
    /* storage blocked */
  }
  const browser = (navigator.language || '').slice(0, 2).toLowerCase();
  return isLanguage(browser) ? browser : FALLBACK;
}

function syncDocument(lng: string) {
  document.documentElement.lang = lng;
}

void i18n.use(initReactI18next).init({
  resources,
  lng: detectLanguage(),
  fallbackLng: FALLBACK,
  supportedLngs: LANGUAGES,
  defaultNS: 'common',
  ns: Object.keys(resources[FALLBACK] ?? {}),
  interpolation: { escapeValue: false },
  returnNull: false,
});
syncDocument(i18n.language);

i18n.on('languageChanged', (lng) => {
  syncDocument(lng);
  try {
    localStorage.setItem(STORAGE_KEY, lng);
  } catch {
    /* storage blocked */
  }
});

/** The active language, narrowed to the supported set. */
export function currentLanguage(): Language {
  return isLanguage(i18n.resolvedLanguage) ? i18n.resolvedLanguage : FALLBACK;
}

export { i18n };
