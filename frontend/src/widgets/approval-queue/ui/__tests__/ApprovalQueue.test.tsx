import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/shared/api/axios-instance';
import { renderWithProviders } from '@/test/render';
import { ApprovalQueue } from '../ApprovalQueue';

const HOUR_MS = 60 * 60 * 1000;

const pending = [
  {
    thread_id: 't1',
    title: 'Send the report',
    updated_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 72 * HOUR_MS).toISOString(),
    interrupt: {
      kind: 'approval_required',
      actions: [
        { action_id: 'a', tool_name: 'send_email', args: {}, risk: 'medium', reason: 'r' },
        { action_id: 'b', tool_name: 'delete_file', args: {}, risk: 'high', reason: 'r' },
      ],
    },
  },
  {
    thread_id: 't2',
    title: '',
    updated_at: new Date().toISOString(),
    expires_at: new Date(Date.now() - HOUR_MS).toISOString(),
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

  it('lists pending threads linking to the chat, grouped by kind', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: pending });
    renderWithProviders(<ApprovalQueue />);
    const link = await screen.findByRole('link', { name: /Send the report/ });
    expect(link).toHaveAttribute('href', '/app/chat/t1');
    expect(link).toHaveTextContent('Send email, delete_file');
    expect(link).toHaveTextContent('High risk');
    expect(link).toHaveTextContent('2 actions');
    const second = screen.getByRole('link', { name: /New conversation/ });
    expect(second).toHaveTextContent('1 action');
    expect(screen.getByRole('heading', { name: /Waiting for approval/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Outcome unknown/ })).toBeInTheDocument();
    expect(vi.spyOn(api, 'get')).toHaveBeenCalledWith('/approvals/pending');
  });

  it('shows when each request expires, and when it already has', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: pending });
    renderWithProviders(<ApprovalQueue />);
    expect(await screen.findByRole('link', { name: /Send the report/ })).toHaveTextContent(
      'Expires in 3 days',
    );
    expect(screen.getByRole('link', { name: /New conversation/ })).toHaveTextContent('Expired');
  });

  it('tolerates a backend that sends no expiry', async () => {
    const [first] = pending;
    vi.spyOn(api, 'get').mockResolvedValue({ data: [{ ...first, expires_at: undefined }] });
    renderWithProviders(<ApprovalQueue />);
    const link = await screen.findByRole('link', { name: /Send the report/ });
    expect(link).not.toHaveTextContent(/expire/i);
  });

  it('dismisses a request after confirming, without opening the conversation', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: pending });
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { run: { status: 'running' } } });
    renderWithProviders(<ApprovalQueue />);
    await userEvent.click(await screen.findByRole('button', { name: 'Dismiss: Send the report' }));
    expect(post).not.toHaveBeenCalled();
    await userEvent.click(await screen.findByRole('button', { name: 'Dismiss request' }));
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/threads/t1/dismiss');
    });
  });

  it('shows an empty state', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: [] });
    renderWithProviders(<ApprovalQueue />);
    expect(await screen.findByText(/nothing is waiting/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Nothing waiting for you' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to chat' })).toHaveAttribute('href', '/app/chat');
  });

  it('offers a retry when loading fails', async () => {
    const get = vi.spyOn(api, 'get').mockRejectedValueOnce(new Error('boom'));
    get.mockResolvedValue({ data: [] });
    renderWithProviders(<ApprovalQueue />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load pending approvals.');
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText(/nothing is waiting/i)).toBeInTheDocument();
  });
});
