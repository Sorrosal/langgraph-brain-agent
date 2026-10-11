import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CodeBlock } from '../code-block';

describe('CodeBlock', () => {
  it('copies the code to the clipboard and confirms', async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    render(<CodeBlock code="npm ci" label="install commands" />);

    await user.click(screen.getByRole('button', { name: 'Copy install commands' }));

    expect(writeText).toHaveBeenCalledWith('npm ci');
    expect(await screen.findByText('Copied')).toBeInTheDocument();
  });
});
