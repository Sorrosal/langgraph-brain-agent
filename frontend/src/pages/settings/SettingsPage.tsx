import { Moon, Sun } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useTheme } from '@/app/providers/ThemeProvider';
import { useAuthStore } from '@/features/auth';
import { UserAvatar } from '@/entities/user';
import { env } from '@/shared/config/env';
import { currentLanguage, LANGUAGES } from '@/shared/i18n';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card';
import { Separator } from '@/shared/ui/separator';

interface FieldProps {
  label: string;
  children: React.ReactNode;
}

function Field({ label, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-sm font-medium">{label}</dt>
      <dd className="font-medium break-words">{children}</dd>
    </div>
  );
}

interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
  lang?: string;
}

interface SegmentedProps<T extends string> {
  name: string;
  label: string;
  value: T;
  options: readonly SegmentedOption<T>[];
  onChange: (value: T) => void;
}

/** Native radios under the hood, so keyboard and screen readers behave like a radio group. */
function Segmented<T extends string>({ name, label, value, options, onChange }: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="bg-muted inline-flex w-fit max-w-full gap-1 rounded-[var(--radius-md)] p-1"
    >
      {options.map((option) => (
        <label key={option.value} lang={option.lang} className="relative cursor-pointer">
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={option.value === value}
            onChange={() => {
              onChange(option.value);
            }}
            className="peer sr-only"
          />
          <span className="text-muted-foreground hover:text-foreground peer-checked:bg-elevated peer-checked:text-foreground peer-checked:shadow-e1 peer-focus-visible:ring-ring flex min-h-10 items-center gap-2 rounded-[var(--radius-sm)] px-3.5 text-sm font-medium whitespace-nowrap transition-colors peer-focus-visible:ring-2 [&_svg]:size-4">
            {option.icon}
            {option.label}
          </span>
        </label>
      ))}
    </div>
  );
}

interface PreferenceRowProps {
  label: string;
  hint: string;
  children: React.ReactNode;
}

function PreferenceRow({ label, hint, children }: PreferenceRowProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-muted-foreground text-sm">{hint}</p>
      </div>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const { t, i18n } = useTranslation('settings');
  const { theme, setTheme } = useTheme();
  const user = useAuthStore((state) => state.user);

  // `useTranslation` re-renders on language change, so reading the current language here is safe.
  const language = currentLanguage();

  return (
    <div className="animate-fade-in mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="text-muted-foreground mt-1 text-sm">{t('subtitle')}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t('profile.title')}</CardTitle>
          <CardDescription>{t('profile.description')}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5 sm:flex-row sm:items-start">
          {user && <UserAvatar user={user} size="lg" />}
          <dl className="grid min-w-0 flex-1 gap-4 sm:grid-cols-[1fr_1fr_auto]">
            <Field label={t('profile.name')}>{user?.display_name || '—'}</Field>
            <Field label={t('profile.email')}>{user?.email ?? '—'}</Field>
            <Field label={t('profile.role')}>
              {user ? <Badge variant="default">{t(`roles.${user.role}`)}</Badge> : '—'}
            </Field>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('preferences.title')}</CardTitle>
          <CardDescription>{t('preferences.description')}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <PreferenceRow label={t('preferences.language')} hint={t('preferences.languageHint')}>
            <Segmented
              name="language"
              label={t('preferences.language')}
              value={language}
              options={LANGUAGES.map((lng) => ({
                value: lng,
                label: t(`common:language.${lng}`),
                lang: lng,
              }))}
              onChange={(lng) => {
                void i18n.changeLanguage(lng);
              }}
            />
          </PreferenceRow>
          <Separator />
          <PreferenceRow label={t('preferences.theme')} hint={t('preferences.themeHint')}>
            <Segmented
              name="theme"
              label={t('preferences.theme')}
              value={theme}
              options={[
                { value: 'light', label: t('preferences.light'), icon: <Sun aria-hidden="true" /> },
                { value: 'dark', label: t('preferences.dark'), icon: <Moon aria-hidden="true" /> },
              ]}
              onChange={setTheme}
            />
          </PreferenceRow>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('application.title')}</CardTitle>
          <CardDescription>{t('application.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Field label={t('application.apiUrl')}>
              <span className="font-mono text-sm break-all">{env.VITE_API_URL}</span>
            </Field>
            <Field label={t('application.appName')}>{env.VITE_APP_NAME}</Field>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
