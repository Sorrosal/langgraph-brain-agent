import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { toast } from 'sonner';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';
import { ApiError } from '@/shared/api/api-error';
import { api } from '@/shared/api/axios-instance';
import { MessageComposer } from '../MessageComposer';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

function renderComposer(disabled = false) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  const onSubmitting = vi.fn();
  const onSubmitFailed = vi.fn();
  const handlers = { onSubmitting, onSubmitFailed };
  render(<MessageComposer threadId="t1" disabled={disabled} {...handlers} />, { wrapper: Wrapper });
  return { onSubmitting, onSubmitFailed, box: screen.getByRole('textbox', { name: /message/i }) };
}

describe('MessageComposer', () => {
  let post: MockInstance<typeof api.post>;

  beforeEach(() => {
    vi.mocked(toast.error).mockClear();
    vi.restoreAllMocks();
    post = vi.spyOn(api, 'post').mockResolvedValue({ data: { run: { status: 'running' } } });
  });

  it('sends on Enter, clears the box and reports the started run', async () => {
    const { onSubmitting, box } = renderComposer();
    await userEvent.type(box, 'hello{Enter}');
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/threads/t1/messages', { content: 'hello' });
    });
    await waitFor(() => {
      expect(onSubmitting).toHaveBeenCalled();
    });
    expect(box).toHaveValue('');
  });

  it('inserts a newline on Shift+Enter without sending', async () => {
    const { box } = renderComposer();
    await userEvent.type(box, 'a{Shift>}{Enter}{/Shift}b');
    expect(box).toHaveValue('a\nb');
    expect(post).not.toHaveBeenCalled();
  });

  it('does not send blank messages', async () => {
    const { box } = renderComposer();
    await userEvent.type(box, '   {Enter}');
    expect(post).not.toHaveBeenCalled();
  });

  it('is disabled while a run is active or awaiting approval', () => {
    const { box } = renderComposer(true);
    expect(box).toBeDisabled();
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled();
  });

  it('explains a 409 (busy) with a toast and keeps the text', async () => {
    post.mockRejectedValue(new ApiError('Thread is busy', 409, { code: 'thread_busy' }));
    const { box, onSubmitting, onSubmitFailed } = renderComposer();
    await userEvent.type(box, 'hello{Enter}');
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/busy/i));
    });
    expect(box).toHaveValue('hello');
    expect(onSubmitting).toHaveBeenCalled();
    expect(onSubmitFailed).toHaveBeenCalled();
  });

  it('tells the user how long to wait on a 429', async () => {
    post.mockRejectedValue(new ApiError('Too many requests', 429, { retryAfter: 7 }));
    const { box } = renderComposer();
    await userEvent.type(box, 'hello{Enter}');
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('7 seconds'));
    });
  });
});
