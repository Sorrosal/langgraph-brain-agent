import { create } from 'zustand';

export type NotificationType = 'info' | 'success' | 'warning' | 'error';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  isRead: boolean;
  createdAt: Date;
}

interface NotificationsState {
  notifications: Notification[];
  unreadCount: number;
  addNotification: (notification: Omit<Notification, 'id' | 'isRead' | 'createdAt'>) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
}

export const useNotificationsStore = create<NotificationsState>()((set, get) => ({
  notifications: [
    {
      id: '1',
      type: 'info',
      title: 'Welcome to React Spark',
      message: 'Your template is ready. Start building amazing things!',
      isRead: false,
      createdAt: new Date(),
    },
  ],
  get unreadCount() {
    return get().notifications.filter((n) => !n.isRead).length;
  },

  addNotification: (notification) => {
    set((state) => ({
      notifications: [
        {
          ...notification,
          id: crypto.randomUUID(),
          isRead: false,
          createdAt: new Date(),
        },
        ...state.notifications,
      ],
    }));
  },

  markAsRead: (id) => {
    set((state) => ({
      notifications: state.notifications.map((n) => (n.id === id ? { ...n, isRead: true } : n)),
    }));
  },

  markAllAsRead: () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, isRead: true })),
    }));
  },

  removeNotification: (id) => {
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    }));
  },

  clearAll: () => {
    set({ notifications: [] });
  },
}));
