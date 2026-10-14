import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuthStore } from '@/features/auth';
import { api } from '@/shared/api/axios-instance';
import { renderWithProviders } from '@/test/render';
import { OrgKnowledge } from '../OrgKnowledge';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const item = {
  id: 'k1',
  kind: 'fact',
  text: 'Invoices are paid on the 5th',
  source_thread_id: null,
  created_at: '2026-01-01T00:00:00Z',
  score: null,
};

function signIn(role: 'admin' | 'operator') {
  useAuthStore.setState({
    token: 't',
    expiresAt: Date.now() + 60_000,
    user: { id: 'u1', email: 'a@b.co', display_name: 'A', role, created_at: '2026-01-01' },
  });
}

describe('OrgKnowledge', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue({ data: [item] });
  });

  afterEach(() => {
    useAuthStore.getState().clearSession();
  });

  it('is read-only for operators', async () => {
    signIn('operator');
    renderWithProviders(<OrgKnowledge />);
    expect(await screen.findByText('Invoices are paid on the 5th')).toBeInTheDocument();
    expect(vi.spyOn(api, 'get')).toHaveBeenCalledWith('/org-knowledge');
    expect(screen.getByText(/Only administrators can add or remove/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add knowledge' })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Delete organisation knowledge' }),
    ).not.toBeInTheDocument();
  });

  it('lets admins add, validating empty text, and invalidates the list', async () => {
    signIn('admin');
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: item });
    const client = renderWithProviders(<OrgKnowledge />);
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    await screen.findByText('Invoices are paid on the 5th');

    await userEvent.click(screen.getByRole('button', { name: 'Add knowledge' }));
    expect(await screen.findByText('Enter some text')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText('Organisation knowledge text'), 'We close at 6pm');
    await userEvent.click(screen.getByRole('button', { name: 'Add knowledge' }));
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/org-knowledge', { text: 'We close at 6pm' });
    });
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['org-knowledge'] });
    });
  });

  it('lets admins delete only after confirmation', async () => {
    signIn('admin');
    const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: null });
    renderWithProviders(<OrgKnowledge />);
    await userEvent.click(
      await screen.findByRole('button', { name: 'Delete organisation knowledge' }),
    );
    expect(del).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => {
      expect(del).toHaveBeenCalledWith('/org-knowledge/k1');
    });
  });

  it('shows the empty state', async () => {
    signIn('operator');
    vi.spyOn(api, 'get').mockResolvedValue({ data: [] });
    renderWithProviders(<OrgKnowledge />);
    expect(await screen.findByText('No organisation knowledge yet.')).toBeInTheDocument();
  });

  it('shows an error state and retries', async () => {
    signIn('operator');
    const get = vi.spyOn(api, 'get').mockRejectedValueOnce(new Error('boom'));
    get.mockResolvedValue({ data: [item] });
    renderWithProviders(<OrgKnowledge />);
    expect(await screen.findByText('Could not load organisation knowledge.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Invoices are paid on the 5th')).toBeInTheDocument();
  });
});
