import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ThemeProvider } from '@/app/providers/ThemeProvider';
import { useAuthStore } from '@/features/auth';
import { i18n } from '@/shared/i18n';
import SettingsPage from '../SettingsPage';

function renderPage() {
  render(
    <ThemeProvider>
      <SettingsPage />
    </ThemeProvider>,
  );
}

describe('SettingsPage', () => {
  beforeEach(() => {
    localStorage.setItem('theme', 'light');
    useAuthStore.setState({
      token: 't',
      expiresAt: Date.now() + 60_000,
      user: {
        id: 'u1',
        email: 'ada@example.com',
        display_name: 'Ada Lovelace',
        role: 'operator',
        created_at: '2026-01-01T00:00:00Z',
      },
    });
  });

  afterEach(async () => {
    document.documentElement.classList.remove('dark');
    await i18n.changeLanguage('en');
  });

  it('shows the profile with a translated role', () => {
    renderPage();
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('ada@example.com')).toBeInTheDocument();
    expect(screen.getByText('Operator')).toBeInTheDocument();
  });

  it('switches the whole page to Spanish from the language preference', async () => {
    renderPage();
    await userEvent.click(screen.getByRole('radio', { name: 'Español' }));
    expect(await screen.findByRole('heading', { name: 'Ajustes' })).toBeInTheDocument();
    expect(screen.getByText('Operador')).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('es');
  });

  it('applies the dark theme from the theme preference', async () => {
    renderPage();
    expect(screen.getByRole('radio', { name: 'Light' })).toBeChecked();
    await userEvent.click(screen.getByRole('radio', { name: 'Dark' }));
    expect(document.documentElement).toHaveClass('dark');
    expect(screen.getByRole('radio', { name: 'Dark' })).toBeChecked();
  });
});
