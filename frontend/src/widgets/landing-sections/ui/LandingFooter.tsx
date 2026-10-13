import { useTranslation } from 'react-i18next';
import { GITHUB_URL } from '@/shared/config/links';

export function LandingFooter() {
  const { t } = useTranslation('landing');

  return (
    <footer className="text-muted-foreground mt-8 border-t py-8 text-center text-sm">
      <p>
        {t('footer.license')}{' '}
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer"
          className="text-brand-ink hover:text-foreground font-medium underline underline-offset-4"
        >
          {t('footer.github')}
        </a>
      </p>
    </footer>
  );
}
