import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/api-error';
import { api } from '@/shared/api/axios-instance';
import { renderWithProviders } from '@/test/render';
import { ContactsTab, DealsTab, EmailsTab, TasksTab } from '../DataTabs';

const contact = {
  id: 'c1',
  name: 'Ada Lovelace',
  email: 'ada@acme.io',
  company: 'Acme',
  phone: null,
  tags: ['vip'],
  created_at: '2026-01-01T00:00:00Z',
};

describe('data tables', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders contact rows and searches with q', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: [contact] });
    renderWithProviders(<ContactsTab />);
    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('vip')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Search contacts'), 'ada');
    await waitFor(() => {
      expect(get).toHaveBeenCalledWith('/crm/contacts', { params: { q: 'ada', limit: 100 } });
    });
  });

  it('formats deal amounts as currency and filters by stage', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({
      data: [
        {
          id: 'd1',
          contact_id: 'c1',
          title: 'Renewal',
          amount: '12000.00',
          currency: 'USD',
          stage: 'won',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
    });
    renderWithProviders(<DealsTab />);
    expect(await screen.findByText('$12,000.00')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Filter by stage'), 'lead');
    await waitFor(() => {
      expect(get).toHaveBeenCalledWith('/crm/deals', { params: { limit: 100, stage: 'lead' } });
    });
  });

  it('shows an empty state for tasks', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: [] });
    renderWithProviders(<TasksTab />);
    expect(await screen.findByText('No tasks found.')).toBeInTheDocument();
    expect(
      screen.getByText(/Create a task to follow up with Globex on Friday/),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open chat' })).toHaveAttribute('href', '/app/chat');
  });

  it('says nothing matches, without suggesting new records, when a filter is active', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: [] });
    renderWithProviders(<TasksTab />);
    await screen.findByText('No tasks found.');
    await userEvent.selectOptions(screen.getByLabelText('Filter by status'), 'done');
    expect(
      await screen.findByText('Nothing matches the current search or filters.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Open chat' })).not.toBeInTheDocument();
  });

  it('shows translated badges, a row count and flags overdue tasks', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: [
        {
          id: 't1',
          title: 'Call Globex',
          description: '',
          due_date: '2020-01-05',
          priority: 'high',
          status: 'open',
          assignee: null,
          created_at: '2020-01-01T00:00:00Z',
        },
      ],
    });
    renderWithProviders(<TasksTab />);
    expect(await screen.findByText('Call Globex')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Open', { selector: 'div' })).toBeInTheDocument();
    expect(screen.getByText('Jan 5, 2020')).toBeInTheDocument();
    expect(screen.getByText('Overdue')).toBeInTheDocument();
    expect(screen.getByText('1 task')).toBeInTheDocument();
  });

  it('shows an error state for emails, queries the inbox by default and retries', async () => {
    const get = vi.spyOn(api, 'get').mockRejectedValue(new ApiError('boom', 500));
    renderWithProviders(<EmailsTab />);
    expect(await screen.findByText('Could not load emails.')).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith('/emails', {
      params: { folder: 'inbox', q: '', limit: 100 },
    });
    get.mockClear();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await waitFor(() => {
      expect(get).toHaveBeenCalledTimes(1);
    });
  });
});
