import { House, RotateCw, TriangleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useRouteError } from 'react-router-dom';
import { Button } from '@/shared/ui/button';

/** Router `errorElement`: a failed lazy chunk or render error shows a retry, not a blank screen. */
export function RouteError() {
  const { t } = useTranslation('landing');
  const error = useRouteError();
  const detail = error instanceof Error ? error.message : null;
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div
        role="alert"
        className="glass animate-slide-up flex w-full max-w-md flex-col items-center gap-3 rounded-[var(--radius-xl)] p-8 text-center sm:p-10"
      >
        <span className="bg-danger-bg text-danger-fg flex size-12 items-center justify-center rounded-full">
          <TriangleAlert className="size-6" aria-hidden="true" />
        </span>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{t('routeError.title')}</h1>
        <p className="text-muted-foreground max-w-sm">{t('routeError.description')}</p>
        {detail && (
          <p className="bg-muted text-muted-foreground max-w-full rounded-[var(--radius-sm)] px-2 py-1 font-mono text-xs break-words">
            {detail}
          </p>
        )}
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Button
            size="lg"
            onClick={() => {
              window.location.reload();
            }}
          >
            <RotateCw aria-hidden="true" />
            {t('common:actions.retry')}
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/">
              <House aria-hidden="true" />
              {t('routeError.home')}
            </Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
