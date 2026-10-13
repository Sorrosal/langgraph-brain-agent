import { ArrowRight, ExternalLink } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { GITHUB_URL } from '@/shared/config/links';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { HERO_HIGHLIGHTS } from '../model/hero';

interface LandingHeroProps {
  showAppCta: boolean;
}

export function LandingHero({ showAppCta }: LandingHeroProps) {
  const { t } = useTranslation('landing');

  return (
    <section
      aria-labelledby="hero-title"
      className="mx-auto max-w-4xl px-4 pt-14 pb-12 text-center sm:px-6 sm:pt-24 sm:pb-16"
    >
      <span className="ev-orb animate-fade-in mx-auto block size-14" aria-hidden="true" />
      <h1
        id="hero-title"
        className="animate-slide-up mt-8 text-4xl leading-[1.1] font-semibold tracking-tight text-balance sm:text-6xl"
      >
        {t('hero.name')}
      </h1>
      <p className="text-muted-foreground mx-auto mt-6 max-w-2xl text-lg text-pretty">
        {t('hero.pitch')}
      </p>
      <ul
        className="mt-6 flex flex-wrap justify-center gap-2"
        aria-label={t('hero.highlightsLabel')}
      >
        {HERO_HIGHLIGHTS.map((item) => (
          <li key={item}>
            <Badge variant="default" className="px-3 py-1 text-xs">
              {t(`hero.highlights.${item}`)}
            </Badge>
          </li>
        ))}
      </ul>
      <div className="mt-10 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
        {showAppCta && (
          <Button asChild size="lg">
            <Link to="/app/chat">
              {t('hero.openApp')}
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        )}
        <Button asChild size="lg" variant="outline">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">
            <ExternalLink aria-hidden="true" />
            {t('hero.github')}
          </a>
        </Button>
      </div>
    </section>
  );
}
