import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { Message } from '../../model/message.types';
import { MessageBubble } from '../MessageBubble';

function message(overrides: Partial<Message>): Message {
  return { id: 'm1', role: 'ai', content: '', tool_calls: [], ...overrides };
}

describe('MessageBubble', () => {
  it('preserves newlines in the text', () => {
    render(<MessageBubble message={message({ role: 'human', content: 'line 1\nline 2' })} />);
    const text = screen.getByText(/line 1/);
    expect(text).toHaveClass('whitespace-pre-wrap');
    expect(text.textContent).toBe('line 1\nline 2');
  });

  it('renders tool calls as cards with name and arguments', () => {
    render(
      <MessageBubble
        message={message({
          content: 'Let me check.',
          tool_calls: [{ id: 'c1', name: 'search_web', args: { query: 'weather' } }],
        })}
      />,
    );
    expect(screen.getByText('Let me check.')).toBeInTheDocument();
    expect(screen.getByText('search_web')).toBeInTheDocument();
    expect(screen.getByText('{"query":"weather"}')).toBeInTheDocument();
  });

  it('renders a tool-call-only message without an empty paragraph', () => {
    render(
      <MessageBubble message={message({ tool_calls: [{ id: 'c1', name: 'noop', args: {} }] })} />,
    );
    expect(screen.getByText('noop')).toBeInTheDocument();
    expect(screen.queryByText('', { selector: 'p' })).not.toBeInTheDocument();
  });

  it('shows tool results collapsed until expanded', async () => {
    render(
      <MessageBubble
        message={message({ role: 'tool', content: 'result body', status: 'error' })}
      />,
    );
    const summary = screen.getByText(/Tool result \(error\)/);
    const details = summary.closest('details');
    expect(details).not.toHaveAttribute('open');
    await userEvent.click(summary);
    expect(details).toHaveAttribute('open');
    expect(screen.getByText('result body')).toBeVisible();
  });
});
