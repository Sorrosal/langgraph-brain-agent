import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
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
      tool_calls: [{ id: 'c1', name: 'send_email', args: { to: 'a@b.co' } }],
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
        <ChatPanel threadId="t1" />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Send the report')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Waiting for your approval');
    expect(screen.getByRole('region', { name: 'Action send_email' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Submit decisions' })).toBeDisabled();
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeDisabled();
  });
});
