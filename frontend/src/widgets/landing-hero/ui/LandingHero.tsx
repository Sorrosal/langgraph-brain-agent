import { GITHUB_URL } from '@/shared/config/links';
import { ArrowRight, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { HERO } from '../model/hero';

interface LandingHeroProps {
  showAppCta: boolean;
}

export function LandingHero({ showAppCta }: LandingHeroProps) {
  return (
    <section aria-labelledby="hero-title" className="mx-auto max-w-4xl px-4 py-20 text-center">
      <h1 id="hero-title" className="text-4xl font-bold tracking-tight sm:text-6xl">
        {HERO.name}
      </h1>
      <p className="text-muted-foreground mx-auto mt-6 max-w-2xl text-lg">{HERO.pitch}</p>
      <ul className="mt-6 flex flex-wrap justify-center gap-2" aria-label="Highlights">
        {HERO.highlights.map((item) => (
          <li key={item}>
            <Badge variant="secondary">{item}</Badge>
          </li>
        ))}
      </ul>
      <div className="mt-10 flex flex-wrap justify-center gap-3">
        {showAppCta && (
          <Button asChild size="lg">
            <Link to="/app/chat">
              Open the app
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        )}
        <Button asChild size="lg" variant="outline">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">
            <ExternalLink className="mr-2 h-4 w-4" />
            View on GitHub
          </a>
        </Button>
      </div>
    </section>
  );
}
