import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { AgentGraph } from '../ui/AgentGraph';

describe('AgentGraph', () => {
  it('starts with the reason node selected', () => {
    render(<AgentGraph />);
    expect(screen.getByRole('region', { name: 'About reason' })).toBeInTheDocument();
  });

  it('explains the selected node when clicked', async () => {
    const user = userEvent.setup();
    render(<AgentGraph />);

    await user.click(screen.getByRole('button', { name: 'tools' }));

    expect(screen.getByRole('region', { name: 'About tools' })).toHaveTextContent(/tool ledger/i);
    expect(screen.getByRole('button', { name: 'tools' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('is operable with the keyboard', async () => {
    const user = userEvent.setup();
    render(<AgentGraph />);

    screen.getByRole('button', { name: 'await_approval' }).focus();
    await user.keyboard('{Enter}');

    expect(screen.getByRole('region', { name: 'About await_approval' })).toHaveTextContent(
      /interrupt\(\)/,
    );
  });
});
