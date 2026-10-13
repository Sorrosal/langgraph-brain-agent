import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import NotFoundPage from '../NotFoundPage';

describe('NotFoundPage', () => {
  it('explains the missing page and links back home', () => {
    renderWithProviders(<NotFoundPage />);

    expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Back to home' })).toHaveAttribute('href', '/');
  });
});
