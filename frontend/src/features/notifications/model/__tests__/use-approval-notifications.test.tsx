import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PendingApproval } from '@/entities/pending-approval';
import { pendingApprovalKeys } from '@/entities/pending-approval';
import { api } from '@/shared/api/axios-instance';
import { useNotificationsStore } from '../notifications.store';
import { pendingKey, unseenPending, useApprovalNotifications } from '../use-approval-notifications';

function item(threadId: string, actionId: string, title = 'Report'): PendingApproval {
  return {
    thread_id: threadId,
    title,
    updated_at: '2026-01-01T00:00:00Z',
    interrupt: {
      kind: 'approval_required',
      actions: [
        { action_id: actionId, tool_name: 'send_email', args: {}, risk: 'high', reason: 'r' },
      ],
    },
  };
}

describe('unseenPending', () => {
  it('keys by thread and action ids, so a new pause on the same thread counts as new', () => {
    const first = item('t1', 'a');
    const seen = new Set([pendingKey(first)]);
    expect(unseenPending(seen, [first])).toEqual([]);
    expect(unseenPending(seen, [first, item('t1', 'b'), item('t2', 'a')])).toHaveLength(2);
  });
});

describe('useApprovalNotifications', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useNotificationsStore.setState({ notifications: [] });
  });

  it('seeds the first load silently, then notifies once per new pending thread', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: [item('t1', 'a')] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    renderHook(
      () => {
        useApprovalNotifications();
      },
      { wrapper },
    );
    await waitFor(() => {
      expect(client.getQueryData(pendingApprovalKeys.all)).toBeDefined();
    });
    expect(useNotificationsStore.getState().notifications).toHaveLength(0);

    vi.spyOn(api, 'get').mockResolvedValue({ data: [item('t1', 'a'), item('t2', 'b', 'Invoice')] });
    await client.invalidateQueries({ queryKey: pendingApprovalKeys.all });
    await waitFor(() => {
      expect(useNotificationsStore.getState().notifications).toHaveLength(1);
    });
    expect(useNotificationsStore.getState().notifications[0]).toMatchObject({
      type: 'warning',
      title: 'Approval needed',
      message: 'Invoice',
      href: '/app/chat/t2',
    });

    // Same data again: nothing new.
    await client.invalidateQueries({ queryKey: pendingApprovalKeys.all });
    expect(useNotificationsStore.getState().notifications).toHaveLength(1);
  });
});
