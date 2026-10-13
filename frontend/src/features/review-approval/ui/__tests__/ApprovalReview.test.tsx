import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';
import type { ActionRequest, PendingInterrupt } from '@/entities/approval';
import { api } from '@/shared/api/axios-instance';
import { ApprovalReview } from '../ApprovalReview';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const email: ActionRequest = {
  action_id: 'c1',
  tool_name: 'send_email',
  args: { to: 'a@b.co' },
  risk: 'high',
  reason: 'Sends email',
};
const del: ActionRequest = {
  action_id: 'c2',
  tool_name: 'delete_file',
  args: { path: '/x' },
  risk: 'medium',
  reason: 'Deletes',
};

function approval(...actions: ActionRequest[]): PendingInterrupt {
  return { kind: 'approval_required', actions };
}

const uncertain: PendingInterrupt = {
  kind: 'uncertain_execution',
  actions: [
    { action_id: 'u1', tool_name: 'charge_card', args: { amount: 5 }, message: 'Timed out' },
  ],
};

function renderReview(interrupt: PendingInterrupt) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  const onSubmitting = vi.fn();
  const handlers = { onSubmitting, onSubmitFailed: vi.fn() };
  render(<ApprovalReview threadId="t1" interrupt={interrupt} {...handlers} />, {
    wrapper: Wrapper,
  });
  return onSubmitting;
}

function choose(card: string, option: string) {
  const region = screen.getByRole('region', { name: `Action ${card}` });
  const match = Array.from(region.querySelectorAll('button')).find(
    (button) => button.textContent === option,
  );
  if (!match) throw new Error(`no ${option} button in ${card}`);
  return userEvent.click(match);
}

async function replaceText(label: RegExp, text: string) {
  const field = screen.getByLabelText(label);
  await userEvent.clear(field);
  await userEvent.click(field);
  await userEvent.paste(text);
}

function submit() {
  return screen.getByRole('button', { name: /submit decisions/i });
}

describe('ApprovalReview', () => {
  let post: MockInstance<typeof api.post>;

  beforeEach(() => {
    vi.restoreAllMocks();
    post = vi.spyOn(api, 'post').mockResolvedValue({ data: { run: { status: 'running' } } });
  });

  it('keeps submit disabled until every action has a decision', async () => {
    renderReview(approval(email, del));
    expect(submit()).toBeDisabled();
    expect(screen.getAllByText('Needs decision')).toHaveLength(2);
    expect(screen.getByText('0 of 2 decided')).toBeInTheDocument();
    await choose('Send email', 'Approve');
    expect(submit()).toBeDisabled();
    expect(screen.getAllByText('Needs decision')).toHaveLength(1);
    expect(screen.getByText('1 of 2 decided')).toBeInTheDocument();
    await choose('delete_file', 'Reject');
    expect(submit()).toBeEnabled();
    expect(screen.queryByText('Needs decision')).not.toBeInTheDocument();
  });

  it('shows a friendly tool name, the risk, the reason and readable arguments', () => {
    renderReview(
      approval({ ...email, args: { to: 'a@b.co', body: 'Line one\nLine two', urgent: true } }),
    );
    const card = screen.getByRole('region', { name: 'Action Send email' });
    expect(within(card).getByRole('heading', { name: 'Send email' })).toBeInTheDocument();
    expect(within(card).getByText('High risk')).toBeInTheDocument();
    expect(within(card).getByText('Sends email')).toBeInTheDocument();
    expect(within(card).getByText('a@b.co')).toBeInTheDocument();
    expect(within(card).getByLabelText('Body')).toHaveTextContent('Line one Line two');
    expect(within(card).getByText('Yes')).toBeInTheDocument();
    expect(within(card).getByText('Raw JSON')).toBeInTheDocument();
  });

  it('falls back to the raw tool name for unknown tools', () => {
    renderReview(approval(del));
    expect(screen.getByRole('heading', { name: 'delete_file' })).toBeInTheDocument();
    expect(screen.getByText('Medium risk')).toBeInTheDocument();
  });

  it('validates edited JSON as you type', async () => {
    renderReview(approval(email));
    await choose('Send email', 'Edit');
    await replaceText(/arguments/i, '{broken');
    expect(await screen.findByRole('alert')).toHaveTextContent('Arguments must be valid JSON.');
    expect(screen.getByLabelText(/arguments/i)).toHaveAttribute('aria-invalid', 'true');
    await replaceText(/arguments/i, '[1]');
    expect(await screen.findByRole('alert')).toHaveTextContent('Arguments must be a JSON object.');
    await replaceText(/arguments/i, '{"to": "z@z.zz"}');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('re-enables the form and shows the error when sending fails', async () => {
    post.mockRejectedValue(new Error('Server down'));
    renderReview(approval(email));
    await choose('Send email', 'Approve');
    await userEvent.click(submit());
    expect(await screen.findByRole('alert')).toHaveTextContent('Server down');
    await waitFor(() => {
      expect(submit()).toBeEnabled();
    });
  });

  it('posts all decisions at once with the backend payload shape', async () => {
    const onSubmitting = renderReview(approval(email, del));
    await choose('Send email', 'Edit');
    await replaceText(/arguments/i, '{"to": "z@z.zz"}');
    await choose('delete_file', 'Reject');
    await userEvent.type(screen.getByLabelText(/reason/i), 'nope');
    await userEvent.click(submit());

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/threads/t1/approvals', {
        decisions: {
          c1: { type: 'edit', args: { to: 'z@z.zz' } },
          c2: { type: 'reject', reason: 'nope' },
        },
      });
    });
    await waitFor(() => {
      expect(onSubmitting).toHaveBeenCalled();
    });
  });

  it('shows an error and does not post invalid JSON', async () => {
    renderReview(approval(email));
    await choose('Send email', 'Edit');
    await replaceText(/arguments/i, '{broken');
    await userEvent.click(submit());
    expect(await screen.findByRole('alert')).toHaveTextContent('Arguments must be valid JSON.');
    expect(post).not.toHaveBeenCalled();
  });

  it('answers with a message instead of running the tool', async () => {
    renderReview(approval(email));
    await choose('Send email', 'Respond');
    await userEvent.type(screen.getByLabelText(/response/i), 'Use SMS instead');
    await userEvent.click(submit());
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/threads/t1/approvals', {
        decisions: { c1: { type: 'respond', message: 'Use SMS instead' } },
      });
    });
  });

  it('resolves uncertain executions through /uncertain', async () => {
    renderReview(uncertain);
    expect(submit()).toBeDisabled();
    await choose('charge_card', 'Retry');
    await userEvent.click(submit());
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/threads/t1/uncertain', {
        decisions: { u1: { type: 'retry' } },
      });
    });
  });
});
