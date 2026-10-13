import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuthStore } from '@/features/auth';
import { ApiError } from '@/shared/api/api-error';
import { api } from '@/shared/api/axios-instance';
import { renderWithProviders } from '@/test/render';
import { BrainRules } from '../BrainRules';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const rules = {
  version_hash: 'abcdef123456',
  persona: 'A careful assistant',
  guidelines: [
    { id: 'g1', text: 'Be concise', priority: 1 },
    { id: 'g2', text: 'Cite sources', priority: 5 },
  ],
  hard_rules: [
    {
      id: 'no-wire',
      description: 'Wires need approval',
      when: { tool: 'send_wire' },
      action: 'require_approval',
      risk: 'high',
    },
  ],
  files: [{ name: 'base.yaml', content: 'persona: x' }],
};

function signIn(role: 'admin' | 'operator') {
  useAuthStore.setState({
    token: 't',
    expiresAt: Date.now() + 60_000,
    user: { id: 'u1', email: 'a@b.co', display_name: 'A', role, created_at: '2026-01-01' },
  });
}

describe('BrainRules', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue({ data: rules });
  });

  it('shows version, persona, guidelines by priority and hard rule cards', async () => {
    signIn('operator');
    renderWithProviders(<BrainRules />);
    expect(await screen.findByText('abcdef123456')).toBeInTheDocument();
    expect(screen.getByText('A careful assistant')).toBeInTheDocument();
    expect(screen.getByText('no-wire')).toBeInTheDocument();
    expect(screen.getByText('Requires approval')).toBeInTheDocument();
    expect(screen.getByText('Risk: high')).toBeInTheDocument();
    const [first] = screen.getAllByText(/^P\d$/);
    expect(first).toHaveTextContent('P5');
  });

  it('is read-only for non-admins', async () => {
    signIn('operator');
    renderWithProviders(<BrainRules />);
    expect(await screen.findByLabelText('base.yaml')).toHaveAttribute('readonly');
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Only administrators can edit the rules/)).toBeInTheDocument();
  });

  it('points admins to the chat and discards unsaved edits', async () => {
    signIn('admin');
    renderWithProviders(<BrainRules />);
    const editor = await screen.findByLabelText('base.yaml');
    expect(screen.getByText('update_rules_file')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Discard changes' })).toBeDisabled();

    await userEvent.type(editor, 'x');
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
    expect(editor).toHaveValue('persona: x');
  });

  it('lets an admin save and reports the new version', async () => {
    signIn('admin');
    const put = vi.spyOn(api, 'put').mockResolvedValue({
      data: { filename: 'base.yaml', version_hash: 'deadbeefcafe' },
    });
    renderWithProviders(<BrainRules />);
    const editor = await screen.findByLabelText('base.yaml');
    await userEvent.type(editor, '\nextra: 1');
    await userEvent.click(screen.getByRole('button', { name: 'Save base.yaml' }));

    await waitFor(() => {
      expect(put).toHaveBeenCalledWith('/rules/base.yaml', { content: 'persona: x\nextra: 1' });
    });
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('deadbeef'));
    });
  });

  it('renders the 422 validation details inline', async () => {
    signIn('admin');
    vi.spyOn(api, 'put').mockRejectedValue(
      new ApiError('line 3: unknown field "tol"', 422, { code: 'invalid_rules' }),
    );
    renderWithProviders(<BrainRules />);
    await userEvent.type(await screen.findByLabelText('base.yaml'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Save base.yaml' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('line 3: unknown field "tol"');
  });
});
