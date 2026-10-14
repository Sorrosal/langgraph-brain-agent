import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/api-error';
import { api } from '@/shared/api/axios-instance';
import { ThreadList } from '../ThreadList';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

function thread(id: string, title: string) {
  return { id, title, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' };
}

const threads = [
  thread('t1', 'Quarterly report'),
  thread('t2', 'Reunión con Ana'),
  thread('t3', ''),
];

function Path() {
  return <output data-testid="path">{useLocation().pathname}</output>;
}

function renderList(path = '/app/chat') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <ThreadList />
        <Path />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openMenu(title: string) {
  await userEvent.click(await screen.findByRole('button', { name: `Actions for ${title}` }));
}

describe('ThreadList', () => {
  beforeAll(() => {
    // Radix popper measures its trigger with ResizeObserver, which jsdom lacks.
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe = vi.fn();
        unobserve = vi.fn();
        disconnect = vi.fn();
      },
    );
  });

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(toast.error).mockClear();
    vi.spyOn(api, 'get').mockResolvedValue({ data: threads });
  });

  it('filters conversations by title, ignoring case and accents', async () => {
    renderList();
    await screen.findByRole('link', { name: /Quarterly report/ });
    const search = screen.getByRole('searchbox', { name: 'Search conversations' });

    await userEvent.type(search, 'REUNION');
    expect(screen.getByRole('link', { name: /Reunión con Ana/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Quarterly report/ })).not.toBeInTheDocument();

    await userEvent.clear(search);
    await userEvent.type(search, 'zzz');
    expect(screen.getByText('No conversations match “zzz”.')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Clear search' }));
    expect(screen.getAllByRole('link')).toHaveLength(3);
  });

  it('renames a conversation: Enter saves', async () => {
    const patch = vi.spyOn(api, 'patch').mockResolvedValue({ data: thread('t1', 'Q1 report') });
    renderList();
    await openMenu('Quarterly report');
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Rename' }));

    const box = await screen.findByRole('textbox', { name: 'Title' });
    expect(box).toHaveValue('Quarterly report');
    await userEvent.clear(box);
    await userEvent.type(box, '  Q1 report {Enter}');

    await waitFor(() => {
      expect(patch).toHaveBeenCalledWith('/threads/t1', { title: 'Q1 report' });
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('cancels the rename with Escape without calling the API', async () => {
    const patch = vi.spyOn(api, 'patch');
    renderList();
    await openMenu('Quarterly report');
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Rename' }));
    await userEvent.type(await screen.findByRole('textbox', { name: 'Title' }), 'x{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(patch).not.toHaveBeenCalled();
  });

  it('deletes the open conversation after confirming and leaves it', async () => {
    const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: null });
    renderList('/app/chat/t1');
    await openMenu('Quarterly report');
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Delete' }));

    const dialog = await screen.findByRole('dialog', { name: 'Delete this conversation?' });
    expect(dialog).toHaveTextContent('“Quarterly report”');
    expect(del).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(del).toHaveBeenCalledWith('/threads/t1');
    });
    await waitFor(() => {
      expect(screen.getByTestId('path')).toHaveTextContent(/^\/app\/chat$/);
    });
  });

  it('explains that a busy conversation cannot be deleted', async () => {
    vi.spyOn(api, 'delete').mockRejectedValue(new ApiError('Thread is busy', 409));
    renderList('/app/chat/t2');
    await openMenu('Reunión con Ana');
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Delete' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/busy/i));
    });
    expect(screen.getByTestId('path')).toHaveTextContent('/app/chat/t2');
  });
});
