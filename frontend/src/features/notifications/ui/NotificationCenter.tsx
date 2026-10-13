import {
  Bell,
  BellOff,
  Check,
  CircleAlert,
  CircleCheck,
  Info,
  Trash2,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
import { cn } from '@/shared/lib/cn';
import { formatRelativeTime } from '@/shared/lib/format';
import {
  selectUnreadCount,
  useNotificationsStore,
  type NotificationType,
} from '../model/notifications.store';

const typeStyles: Record<NotificationType, { icon: LucideIcon; tone: string }> = {
  info: { icon: Info, tone: 'text-info-fg' },
  success: { icon: CircleCheck, tone: 'text-success-fg' },
  warning: { icon: TriangleAlert, tone: 'text-warning-fg' },
  error: { icon: CircleAlert, tone: 'text-danger-fg' },
};

export function NotificationCenter() {
  const { t } = useTranslation('shell');
  const { notifications, markAsRead, markAllAsRead, removeNotification } = useNotificationsStore();
  const unreadCount = useNotificationsStore(selectUnreadCount);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative max-md:size-11 [&_svg]:size-5"
          aria-label={
            unreadCount > 0
              ? t('notifications.titleUnread', { count: unreadCount })
              : t('notifications.title')
          }
        >
          <Bell />
          {unreadCount > 0 && (
            <span
              aria-hidden="true"
              className="bg-primary text-primary-foreground text-2xs absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full px-1 font-semibold tabular-nums max-md:top-1.5 max-md:right-1.5"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-[min(22rem,calc(100vw-2rem))] p-0">
        <DropdownMenuLabel className="flex items-center justify-between gap-2 px-4 py-3">
          <span className="font-display">{t('notifications.title')}</span>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="-mr-2 h-8 px-2"
              onClick={() => {
                markAllAsRead();
              }}
            >
              <Check />
              {t('notifications.markAllRead')}
            </Button>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="my-0" />

        {notifications.length === 0 ? (
          <div className="flex flex-col items-center gap-1 px-4 py-8 text-center">
            <span className="bg-muted text-muted-foreground mb-2 flex size-10 items-center justify-center rounded-full">
              <BellOff className="size-5" aria-hidden="true" />
            </span>
            <p className="text-sm font-medium">{t('notifications.empty')}</p>
            <p className="text-muted-foreground text-xs">{t('notifications.emptyHint')}</p>
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto p-1">
            {notifications.map((notification) => {
              const { icon: Icon, tone } = typeStyles[notification.type];
              return (
                <DropdownMenuItem
                  key={notification.id}
                  className={cn(
                    'flex cursor-default items-start gap-3 rounded-[var(--radius-sm)] px-3 py-3',
                    !notification.isRead && 'bg-brand-bg/60',
                  )}
                  onSelect={(e) => {
                    e.preventDefault();
                  }}
                >
                  <Icon className={cn('mt-0.5', tone)} aria-hidden="true" />
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="text-sm font-medium">{notification.title}</span>
                    <p className="text-muted-foreground text-xs">{notification.message}</p>
                    <time
                      dateTime={notification.createdAt.toISOString()}
                      className="text-faint text-2xs"
                    >
                      {formatRelativeTime(notification.createdAt)}
                    </time>
                  </div>
                  <div className="-my-1 -mr-1 flex shrink-0">
                    {!notification.isRead && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-9"
                        aria-label={t('notifications.markRead')}
                        onClick={() => {
                          markAsRead(notification.id);
                        }}
                      >
                        <Check />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-9"
                      aria-label={t('notifications.remove')}
                      onClick={() => {
                        removeNotification(notification.id);
                      }}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </DropdownMenuItem>
              );
            })}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
