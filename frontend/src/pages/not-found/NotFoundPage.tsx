import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from '@/shared/ui/button';

export default function NotFoundPage() {
  const { t } = useTranslation('landing');

  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="glass animate-slide-up flex w-full max-w-md flex-col items-center gap-3 rounded-[var(--radius-xl)] p-8 text-center sm:p-10">
        <span className="ev-orb size-12" aria-hidden="true" />
        <p
          className="font-display text-brand-ink mt-2 text-6xl font-semibold tracking-tight"
          aria-hidden="true"
        >
          404
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">{t('notFound.title')}</h1>
        <p className="text-muted-foreground max-w-sm">{t('notFound.description')}</p>
        <Button asChild size="lg" className="mt-4">
          <Link to="/">
            <ArrowLeft aria-hidden="true" />
            {t('notFound.home')}
          </Link>
        </Button>
      </div>
    </main>
  );
}
