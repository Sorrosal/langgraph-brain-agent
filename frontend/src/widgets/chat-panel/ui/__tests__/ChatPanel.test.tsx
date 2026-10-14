import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/shared/api/axios-instance';
import { ChatPanel } from '../ChatPanel';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const detail = {
  id: 't1',
  title: 'Hello',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  messages: [
    { id: 'm1', role: 'human', content: 'Send the report' },
    {
      id: 'm2',
      role: 'ai',
      content: '',
      tool_calls: [{ id: 'c1', name: 'send_email', args: { to: 'a@b.co' }, message: 'Unclear' }],
    },
  ],
  summary: null,
  pending_interrupt: {
    kind: 'approval_required',
    actions: [
      {
        action_id: 'c1',
        tool_name: 'send_email',
        args: { to: 'a@b.co' },
        risk: 'high',
        reason: 'Sends email',
      },
    ],
  },
  run: { status: 'interrupted' },
  approvals: [],
};

describe('ChatPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue({ data: detail });
  });

  it('shows the history, the inline approval panel and a locked composer', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ChatPanel threadId="t1" />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Send the report')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Waiting for your approval');
    expect(screen.getByRole('region', { name: 'Action Send email' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Submit decisions' })).toBeDisabled();
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeDisabled();
  });

  it('offers Stop while a run is active and cancels it', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { ...detail, pending_interrupt: null, run: { status: 'running' } },
    });
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { run: { status: 'failed' } } });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ChatPanel threadId="t1" />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByRole('button', { name: 'Stop' }));
    expect(post).toHaveBeenCalledWith('/threads/t1/cancel');
  });

  it('does not offer Stop while waiting for an approval, but offers Dismiss', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ChatPanel threadId="t1" />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole('button', { name: 'Dismiss' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Stop' })).not.toBeInTheDocument();
  });

  it.each([
    ['approvals', detail.pending_interrupt, 'Approve'],
    [
      'uncertain',
      {
        kind: 'uncertain_execution',
        actions: [
          { action_id: 'c1', tool_name: 'send_email', args: { to: 'a@b.co' }, message: 'Unclear' },
        ],
      },
      'Retry',
    ],
  ])(
    'restores the %s panel when the POST fails after it unmounted',
    async (endpoint, pending, choice) => {
      vi.spyOn(api, 'get').mockResolvedValue({ data: { ...detail, pending_interrupt: pending } });
      const post = vi.spyOn(api, 'post').mockRejectedValue(new Error('Conflict'));
      const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <ChatPanel threadId="t1" />
          </MemoryRouter>
        </QueryClientProvider>,
      );

      await userEvent.click(await screen.findByRole('button', { name: choice }));
      await userEvent.click(screen.getByRole('button', { name: 'Submit decisions' }));

      expect(post).toHaveBeenCalledWith(`/threads/t1/${endpoint}`, expect.anything());
      await waitFor(() => {
        expect(screen.getByRole('status')).not.toHaveTextContent('Thinking');
      });
      expect(await screen.findByRole('button', { name: 'Submit decisions' })).toBeInTheDocument();
    },
  );
});
