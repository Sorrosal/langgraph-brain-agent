import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { LandingHero } from '../ui/LandingHero';

describe('LandingHero', () => {
  it('shows the app CTA and the GitHub link', () => {
    renderWithProviders(<LandingHero showAppCta />);
    expect(screen.getByRole('heading', { level: 1, name: 'LangGraph Brain Agent' })).toBeVisible();
    expect(screen.getByRole('link', { name: /open the app/i })).toHaveAttribute(
      'href',
      '/app/chat',
    );
    expect(screen.getByRole('link', { name: /view on github/i })).toHaveAttribute(
      'href',
      'https://github.com/Sorrosal/langgraph-brain-agent',
    );
  });

  it('hides the app CTA in landing-only mode', () => {
    renderWithProviders(<LandingHero showAppCta={false} />);
    expect(screen.queryByRole('link', { name: /open the app/i })).not.toBeInTheDocument();
  });
});
