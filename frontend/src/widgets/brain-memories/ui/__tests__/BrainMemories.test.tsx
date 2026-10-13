import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/shared/api/axios-instance';
import { renderWithProviders } from '@/test/render';
import { BrainMemories } from '../BrainMemories';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const memory = {
  id: 'm1',
  kind: 'fact',
  text: 'Works at Acme',
  source_thread_id: null,
  created_at: '2026-01-01T00:00:00Z',
  score: null,
};

describe('BrainMemories', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue({ data: [memory] });
  });

  it('lists memories filtered by kind', async () => {
    renderWithProviders(<BrainMemories />);
    expect(await screen.findByText('Works at Acme')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Filter by kind'), 'episode');
    await waitFor(() => {
      expect(vi.spyOn(api, 'get')).toHaveBeenCalledWith('/memories', {
        params: { kind: 'episode' },
      });
    });
  });

  it('searches semantically after the debounce', async () => {
    renderWithProviders(<BrainMemories />);
    await userEvent.type(screen.getByLabelText('Search memories'), 'employer');
    await waitFor(() => {
      expect(vi.spyOn(api, 'get')).toHaveBeenCalledWith('/memories/search', {
        params: { q: 'employer' },
      });
    });
  });

  it('adds a memory, validates empty text, and invalidates the lists', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: memory });
    const client = renderWithProviders(<BrainMemories />);
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    await screen.findByText('Works at Acme');

    await userEvent.click(screen.getByRole('button', { name: 'Add memory' }));
    expect(await screen.findByText('Enter some text')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('radio', { name: 'Preference' }));
    await userEvent.type(screen.getByLabelText('Memory text'), 'Likes tea');
    await userEvent.click(screen.getByRole('button', { name: 'Add memory' }));
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/memories', { kind: 'preference', text: 'Likes tea' });
    });
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['memories'] });
    });
  });

  it('explains what memories are when there are none', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: [] });
    renderWithProviders(<BrainMemories />);
    expect(await screen.findByText('No memories yet.')).toBeInTheDocument();
    expect(screen.getByText(/the agent also learns them on its own/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open chat' })).toHaveAttribute('href', '/app/chat');
  });

  it('shows an error state and retries', async () => {
    const get = vi.spyOn(api, 'get').mockRejectedValueOnce(new Error('boom'));
    get.mockResolvedValue({ data: [memory] });
    renderWithProviders(<BrainMemories />);
    expect(await screen.findByText('Could not load memories.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Works at Acme')).toBeInTheDocument();
  });

  it('deletes only after confirmation', async () => {
    const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: null });
    const client = renderWithProviders(<BrainMemories />);
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    await userEvent.click(await screen.findByRole('button', { name: 'Delete memory' }));
    expect(del).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => {
      expect(del).toHaveBeenCalledWith('/memories/m1');
    });
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['memories'] });
    });
  });
});
