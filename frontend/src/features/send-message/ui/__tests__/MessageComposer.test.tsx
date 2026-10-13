import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/api-error';
import { describeSendError } from '../../model/send-error';
import { MessageComposer } from '../MessageComposer';

function renderComposer(props: { busy?: boolean; sending?: boolean } = {}) {
  const onSend = vi.fn<(text: string, onSent: () => void) => void>();
  render(
    <MessageComposer busy={props.busy ?? false} sending={props.sending ?? false} onSend={onSend} />,
  );
  return { onSend, box: screen.getByRole('textbox', { name: /message/i }) };
}

describe('MessageComposer', () => {
  it('sends the trimmed text on Enter and clears the box once accepted', async () => {
    const { onSend, box } = renderComposer();
    await userEvent.type(box, '  hello {Enter}');
    expect(onSend).toHaveBeenCalledWith('hello', expect.any(Function));
    expect(box).toHaveValue('  hello ');
    const [[, onSent]] = onSend.mock.calls as [[string, () => void]];
    onSent();
    expect(await screen.findByRole('textbox', { name: /message/i })).toHaveValue('');
  });

  it('keeps the text when the send is not accepted', async () => {
    const { onSend, box } = renderComposer();
    await userEvent.type(box, 'hello{Enter}');
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(box).toHaveValue('hello');
  });

  it('inserts a newline on Shift+Enter without sending', async () => {
    const { onSend, box } = renderComposer();
    await userEvent.type(box, 'a{Shift>}{Enter}{/Shift}b');
    expect(box).toHaveValue('a\nb');
    expect(onSend).not.toHaveBeenCalled();
  });

  it('does not send blank messages', async () => {
    const { onSend, box } = renderComposer();
    await userEvent.type(box, '   {Enter}');
    expect(onSend).not.toHaveBeenCalled();
  });

  it('is locked while a run is active or awaiting approval', () => {
    const { box } = renderComposer({ busy: true });
    expect(box).toBeDisabled();
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled();
  });

  it('does not send twice while the request is in flight', async () => {
    const { onSend, box } = renderComposer({ sending: true });
    await userEvent.type(box, 'hello{Enter}');
    expect(onSend).not.toHaveBeenCalled();
  });
});

describe('describeSendError', () => {
  it('explains a 409 (busy)', () => {
    expect(describeSendError(new ApiError('Thread is busy', 409))).toMatch(/busy/i);
  });

  it('tells the user how long to wait on a 429', () => {
    expect(describeSendError(new ApiError('Too many', 429, { retryAfter: 7 }))).toContain(
      '7 seconds',
    );
  });

  it('falls back to a generic message for unknown errors', () => {
    expect(describeSendError(new Error('boom'))).toMatch(/could not send/i);
  });
});
