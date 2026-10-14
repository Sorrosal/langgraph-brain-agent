import { fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/shared/api/axios-instance';
import { renderWithProviders } from '@/test/render';
import { KnowledgeGraph } from '../KnowledgeGraph';

const graph = {
  nodes: [
    { id: 'user', type: 'user', label: 'Ana' },
    { id: 'kind:fact', type: 'memory_kind', label: 'fact' },
    {
      id: 'mem:1',
      type: 'memory',
      label: 'Ada works at Globex',
      detail: 'Ada Lovelace works at Globex as CTO',
      group: 'episode',
      created_at: '2026-01-01T00:00:00Z',
    },
    { id: 'contact:1', type: 'contact', label: 'Ada Lovelace', detail: 'ada@globex.com' },
    { id: 'company:globex', type: 'company', label: 'Globex' },
    // A type the UI has never heard of, with a malformed optional field.
    { id: 'x:1', type: 'hologram', label: 'Mystery', detail: 42 },
  ],
  edges: [
    { source: 'user', target: 'kind:fact', kind: 'has' },
    { source: 'kind:fact', target: 'mem:1', kind: 'has' },
    { source: 'mem:1', target: 'contact:1', kind: 'mentions' },
    { source: 'contact:1', target: 'company:globex', kind: 'works_at' },
    { source: 'contact:1', target: 'ghost', kind: 'works_at' },
  ],
  truncated: false,
};

const node = (name: string) => screen.getByRole('button', { name });

describe('KnowledgeGraph', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue({ data: graph });
  });

  it('renders every node as a focusable button and a stats line', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: graph });
    renderWithProviders(<KnowledgeGraph />);
    const memory = await screen.findByRole('button', { name: 'Memory: Ada works at Globex' });
    expect(memory).toHaveAttribute('tabindex', '0');
    expect(node('You: Ana')).toBeInTheDocument();
    expect(node('Other: Mystery')).toBeInTheDocument();
    expect(screen.getByText('1 memory · 1 contact · 1 company')).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith('/brain/graph');
  });

  it('selects a node with Enter and walks to a neighbour from the panel', async () => {
    renderWithProviders(<KnowledgeGraph />);
    fireEvent.keyDown(await screen.findByRole('button', { name: 'Contact: Ada Lovelace' }), {
      key: 'Enter',
    });

    const panel = screen.getByRole('complementary', { name: 'Selected item' });
    expect(within(panel).getByText('ada@globex.com')).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole('button', { name: 'Globex' }));
    expect(within(panel).getByRole('heading', { name: 'Globex' })).toBeInTheDocument();
    expect(node('Company: Globex')).toHaveAttribute('aria-pressed', 'true');

    await userEvent.click(within(panel).getByRole('button', { name: 'Close details' }));
    expect(within(panel).getByText(/Select an item/)).toBeInTheDocument();
  });

  it('shows the memory detail, group and date in the panel', async () => {
    renderWithProviders(<KnowledgeGraph />);
    fireEvent.keyDown(await screen.findByRole('button', { name: 'Memory: Ada works at Globex' }), {
      key: ' ',
    });
    const panel = screen.getByRole('complementary', { name: 'Selected item' });
    expect(within(panel).getByText('Ada Lovelace works at Globex as CTO')).toBeInTheDocument();
    expect(within(panel).getByText('Episode')).toBeInTheDocument();
    expect(within(panel).getByText(/^Added /)).toBeInTheDocument();
  });

  it('counts search hits and toggles a type off', async () => {
    renderWithProviders(<KnowledgeGraph />);
    await userEvent.type(await screen.findByLabelText('Search the graph'), 'globex');
    expect(screen.getByText('3 matches')).toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText('Search the graph'));
    await userEvent.click(screen.getByRole('button', { name: /^Contact\s?1$/ }));
    expect(screen.queryByRole('button', { name: 'Contact: Ada Lovelace' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Contact\s?1$/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('explains how the graph fills up when only the user exists', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: { nodes: [{ id: 'user', type: 'user', label: 'Ana' }], edges: [] },
    });
    renderWithProviders(<KnowledgeGraph />);
    expect(await screen.findByText('Nothing to show yet.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open chat' })).toHaveAttribute('href', '/app/chat');
  });

  it('shows an error state and retries', async () => {
    vi.spyOn(api, 'get')
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValue({ data: graph });
    renderWithProviders(<KnowledgeGraph />);
    expect(await screen.findByText('Could not load the knowledge graph.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('button', { name: 'You: Ana' })).toBeInTheDocument();
  });
});
