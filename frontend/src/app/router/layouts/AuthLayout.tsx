import { Brain, DatabaseZap, UserCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, Outlet } from 'react-router-dom';
import { useTheme } from '@/app/providers/ThemeProvider';
import { LanguageSwitcher } from '@/features/switch-language';
import { env } from '@/shared/config/env';
import { ThemeToggle } from '@/widgets/theme-toggle';

const POINTS = [
  { key: 'approval', icon: UserCheck },
  { key: 'crashSafe', icon: DatabaseZap },
  { key: 'memory', icon: Brain },
] as const;

/** Auth shell: brand + value points on the left (large screens), the form in a glass card. */
export function AuthLayout() {
  const { t } = useTranslation('auth');
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-dvh">
      <div className="mx-auto flex min-h-dvh w-full max-w-6xl flex-col px-4 py-4 sm:px-8 lg:px-10">
        <header className="flex items-center justify-between">
          <Link
            to="/"
            className="focus-visible:ring-ring flex items-center gap-2.5 rounded-[var(--radius-md)] py-1 focus-visible:ring-2 focus-visible:outline-none"
          >
            <span className="ev-orb size-7" aria-hidden="true" />
            <span className="font-display text-lg font-semibold tracking-tight">
              {env.VITE_APP_NAME}
            </span>
          </Link>
          <div className="flex items-center gap-1">
            <LanguageSwitcher />
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
        </header>

        <div className="grid flex-1 items-center gap-12 py-8 lg:grid-cols-[1.1fr_1fr] lg:gap-20">
          <aside className="hidden flex-col gap-10 lg:flex">
            <p className="font-display max-w-lg text-4xl leading-[1.15] font-semibold tracking-tight text-balance xl:text-5xl">
              {t('layout.tagline')}
            </p>
            <ul className="flex max-w-md flex-col gap-5">
              {POINTS.map(({ key, icon: Icon }) => (
                <li key={key} className="flex items-start gap-4">
                  <span className="bg-brand-bg text-brand-ink flex size-10 shrink-0 items-center justify-center rounded-[var(--radius-md)]">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="font-medium">{t(`layout.points.${key}.title`)}</p>
                    <p className="text-muted-foreground mt-0.5 text-sm">
                      {t(`layout.points.${key}.text`)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </aside>

          <main className="mx-auto w-full max-w-md">
            <div className="glass animate-slide-up rounded-[var(--radius-xl)] p-6 sm:p-8">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
