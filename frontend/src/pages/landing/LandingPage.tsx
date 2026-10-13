import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '@/features/switch-language';
import { Section } from '@/shared/ui/section';
import { AgentGraph } from '@/widgets/agent-graph';
import { CrashWalkthrough } from '@/widgets/crash-walkthrough';
import { LandingHero } from '@/widgets/landing-hero';
import {
  Architecture,
  Brain,
  HumanInTheLoop,
  LandingFooter,
  Quickstart,
  WhatItDoes,
} from '@/widgets/landing-sections';

interface LandingPageProps {
  showAppCta: boolean;
  /** Rendered in the top bar; supplied by the app layer, which owns the theme. */
  themeToggle?: React.ReactNode;
}

export default function LandingPage({ showAppCta, themeToggle }: LandingPageProps) {
  const { t } = useTranslation('landing');

  return (
    <div className="text-foreground min-h-dvh">
      <a
        href="#main"
        className="bg-elevated text-foreground shadow-e2 focus-visible:ring-ring sr-only z-50 rounded-[var(--radius-md)] px-4 py-2 text-sm font-medium focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus-visible:ring-2"
      >
        {t('header.skipToContent')}
      </a>
      <header className="bg-glass sticky top-0 z-30 border-b backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-2 sm:px-6">
          <span className="flex items-center gap-2.5">
            <span className="ev-orb size-6" aria-hidden="true" />
            <span className="font-display font-semibold tracking-tight">Brain Agent</span>
          </span>
          <div className="flex items-center gap-1">
            <LanguageSwitcher />
            {themeToggle}
          </div>
        </div>
      </header>
      <main id="main">
        <LandingHero showAppCta={showAppCta} />
        <WhatItDoes />
        <Section id="graph" title={t('graph.title')} description={t('graph.description')}>
          <AgentGraph />
        </Section>
        <Section
          id="crash-safety"
          title={t('crashSafety.title')}
          description={t('crashSafety.description')}
        >
          <CrashWalkthrough />
        </Section>
        <HumanInTheLoop />
        <Brain />
        <Architecture />
        <Quickstart />
      </main>
      <LandingFooter />
    </div>
  );
}
