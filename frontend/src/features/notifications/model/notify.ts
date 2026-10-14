import type { PendingApproval } from '@/entities/pending-approval';
import { i18n } from '@/shared/i18n';
import { useNotificationsStore } from './notifications.store';

const chatPath = (threadId: string) => `/app/chat/${encodeURIComponent(threadId)}`;

function threadLabel(title: string): string {
  return title || i18n.t('chat:untitled');
}

/** A thread paused on a decision. Texts are translated when created, in the active language. */
export function notifyApprovalNeeded(item: PendingApproval) {
  useNotificationsStore.getState().addNotification({
    type: 'warning',
    title: i18n.t(
      item.interrupt.kind === 'approval_required'
        ? 'shell:notifications.approvalNeeded'
        : 'shell:notifications.outcomeUnknown',
    ),
    message: threadLabel(item.title),
    href: chatPath(item.thread_id),
  });
}

/** A run ended with an error (a deliberate stop is not one). */
export function notifyRunFailed(thread: { id: string; title: string }) {
  useNotificationsStore.getState().addNotification({
    type: 'error',
    title: i18n.t('shell:notifications.runFailed'),
    message: threadLabel(thread.title),
    href: chatPath(thread.id),
  });
}
