import { render, screen } from '@testing-library/react';
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { i18n } from '@/shared/i18n';
import { useNotificationsStore } from '../../model/notifications.store';
import { NotificationCenter } from '../NotificationCenter';

describe('NotificationCenter', () => {
  beforeEach(() => {
    useNotificationsStore.setState({ notifications: [] });
  });

  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('labels the bell with the unread count, in the active language', async () => {
    render(<NotificationCenter />);
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument();

    act(() => {
      useNotificationsStore.getState().addNotification({ type: 'info', title: 'A', message: 'a' });
    });
    expect(screen.getByRole('button', { name: 'Notifications, 1 unread' })).toBeInTheDocument();

    await act(() => i18n.changeLanguage('es'));
    expect(screen.getByRole('button', { name: 'Notificaciones, 1 sin leer' })).toBeInTheDocument();
  });
});
