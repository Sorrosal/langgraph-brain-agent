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
  return (
    <div className="bg-background text-foreground min-h-screen">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <span className="font-semibold">Brain Agent</span>
        {themeToggle}
      </header>
      <main>
        <LandingHero showAppCta={showAppCta} />
        <WhatItDoes />
        <Section
          id="graph"
          title="How a run flows"
          description="The agent is a LangGraph state graph. Select a node to see what it does and what it guarantees."
        >
          <AgentGraph />
        </Section>
        <Section
          id="crash-safety"
          title="Crash safety, step by step"
          description="What happens when the process dies while an email is being sent."
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
