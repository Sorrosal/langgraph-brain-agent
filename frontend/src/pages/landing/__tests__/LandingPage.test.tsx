import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { i18n } from '@/shared/i18n';
import { renderWithProviders } from '@/test/render';
import LandingPage from '../LandingPage';

const SECTION_HEADINGS = [
  'What it does',
  'How a run flows',
  'Crash safety, step by step',
  'Human in the loop',
  'The brain',
  'Architecture & stack',
  'Quickstart',
];

describe('LandingPage', () => {
  it('renders the hero and every section heading', () => {
    renderWithProviders(<LandingPage showAppCta />);

    expect(screen.getByRole('heading', { level: 1, name: 'LangGraph Brain Agent' })).toBeVisible();
    for (const name of SECTION_HEADINGS) {
      expect(screen.getByRole('heading', { level: 2, name })).toBeVisible();
    }
    expect(screen.getByRole('contentinfo')).toHaveTextContent(/MIT/);
  });

  it('translates the page when the language changes', async () => {
    await i18n.changeLanguage('es');
    try {
      renderWithProviders(<LandingPage showAppCta />);

      expect(screen.getByRole('heading', { level: 2, name: 'Qué hace' })).toBeVisible();
      expect(screen.getByRole('link', { name: /abrir la aplicación/i })).toBeVisible();
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('lists what needs approval and what is blocked', () => {
    renderWithProviders(<LandingPage showAppCta />);

    expect(screen.getByText(/Deal updates above 10000/)).toBeVisible();
    expect(screen.getByText('Deleting CRM records')).toBeVisible();
  });
});
