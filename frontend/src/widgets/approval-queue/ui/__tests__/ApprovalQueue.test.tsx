import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/shared/api/axios-instance';
import { renderWithProviders } from '@/test/render';
import { ApprovalQueue } from '../ApprovalQueue';

const pending = [
  {
    thread_id: 't1',
    title: 'Send the report',
    updated_at: new Date().toISOString(),
    interrupt: {
      kind: 'approval_required',
      actions: [
        { action_id: 'a', tool_name: 'send_email', args: {}, risk: 'high', reason: 'r' },
        { action_id: 'b', tool_name: 'delete_file', args: {}, risk: 'low', reason: 'r' },
      ],
    },
  },
  {
    thread_id: 't2',
    title: '',
    updated_at: new Date().toISOString(),
    interrupt: {
      kind: 'uncertain_execution',
      actions: [{ action_id: 'u', tool_name: 'charge', args: {}, message: 'Timed out' }],
    },
  },
];

describe('ApprovalQueue', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('lists pending threads linking to the chat', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: pending });
    renderWithProviders(<ApprovalQueue />);
    const link = await screen.findByRole('link', { name: /Send the report/ });
    expect(link).toHaveAttribute('href', '/app/chat/t1');
    expect(link).toHaveTextContent('approval');
    expect(link).toHaveTextContent('2 actions');
    const second = screen.getByRole('link', { name: /New conversation/ });
    expect(second).toHaveTextContent('uncertain');
    expect(second).toHaveTextContent('1 action');
    expect(vi.spyOn(api, 'get')).toHaveBeenCalledWith('/approvals/pending');
  });

  it('shows an empty state', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: [] });
    renderWithProviders(<ApprovalQueue />);
    expect(await screen.findByText(/nothing is waiting/i)).toBeInTheDocument();
  });
});
