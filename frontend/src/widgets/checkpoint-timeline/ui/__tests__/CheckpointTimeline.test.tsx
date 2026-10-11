import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/shared/api/axios-instance';
import { renderWithProviders } from '@/test/render';
import { CheckpointTimeline } from '../CheckpointTimeline';

const history = [
  {
    checkpoint_id: 'aaaaaaaa-0003',
    step: 3,
    created_at: '2026-01-01T00:00:03Z',
    source: 'loop',
    writes: ['agent'],
    next: [],
    message_count: 4,
  },
  {
    checkpoint_id: 'bbbbbbbb-0002',
    step: 2,
    created_at: '2026-01-01T00:00:02Z',
    source: 'loop',
    writes: ['tools'],
    next: ['agent'],
    message_count: 3,
  },
  {
    checkpoint_id: 'cccccccc-0001',
    step: 1,
    created_at: null,
    source: 'input',
    writes: [],
    next: ['agent'],
    message_count: 1,
  },
];

describe('CheckpointTimeline', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue({ data: history });
  });

  it('renders the steps in the order returned and requests 50', async () => {
    renderWithProviders(<CheckpointTimeline threadId="t1" />);
    const items = within(await screen.findByRole('list', { name: 'Checkpoints' })).getAllByRole(
      'listitem',
    );
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining('step 3'),
      expect.stringContaining('step 2'),
      expect.stringContaining('step 1'),
    ]);
    expect(items[0]).toHaveTextContent('aaaaaaaa');
    expect(items[1]).toHaveTextContent('wrote: toolsnext: agent');
    expect(items[1]).toHaveTextContent('3 msg');
    expect(vi.spyOn(api, 'get')).toHaveBeenCalledWith('/threads/t1/history', {
      params: { limit: 50 },
    });
  });

  it('shows details of the selected checkpoint', async () => {
    renderWithProviders(<CheckpointTimeline threadId="t1" />);
    await userEvent.click(await screen.findByRole('button', { name: /bbbbbbbb/ }));
    const details = screen.getByLabelText('Checkpoint details');
    expect(details).toHaveTextContent('bbbbbbbb-0002');
    expect(details).toHaveTextContent('loop');
  });

  it('shows an empty state', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: [] });
    renderWithProviders(<CheckpointTimeline threadId="t1" />);
    expect(await screen.findByText('No checkpoints yet.')).toBeInTheDocument();
  });
});
