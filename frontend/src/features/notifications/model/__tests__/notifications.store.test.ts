import { beforeEach, describe, expect, it } from 'vitest';
import { selectUnreadCount, useNotificationsStore } from '../notifications.store';

describe('notifications store', () => {
  beforeEach(() => {
    useNotificationsStore.setState({ notifications: [] });
  });

  it('derives the unread count and updates it when marking as read', () => {
    const { addNotification } = useNotificationsStore.getState();
    addNotification({ type: 'info', title: 'A', message: 'a' });
    addNotification({ type: 'error', title: 'B', message: 'b' });
    expect(selectUnreadCount(useNotificationsStore.getState())).toBe(2);

    const first = useNotificationsStore.getState().notifications[0];
    expect(first).toBeDefined();
    useNotificationsStore.getState().markAsRead(first?.id ?? '');
    expect(selectUnreadCount(useNotificationsStore.getState())).toBe(1);

    useNotificationsStore.getState().markAllAsRead();
    expect(selectUnreadCount(useNotificationsStore.getState())).toBe(0);
  });

  it('does not keep the count in state', () => {
    expect('unreadCount' in useNotificationsStore.getState()).toBe(false);
  });
});
