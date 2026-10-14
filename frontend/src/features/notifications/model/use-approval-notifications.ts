import { useEffect, useRef } from 'react';
import { usePendingApprovals } from '@/entities/pending-approval';
import type { PendingApproval } from '@/entities/pending-approval';
import { notifyApprovalNeeded } from './notify';

/** Identifies one pause: a thread asking about a specific set of actions. */
export function pendingKey(item: PendingApproval): string {
  return `${item.thread_id}:${item.interrupt.actions.map((action) => action.action_id).join(',')}`;
}

/** The items whose key is not in `seen` yet. */
export function unseenPending(
  seen: ReadonlySet<string>,
  items: readonly PendingApproval[],
): PendingApproval[] {
  return items.filter((item) => !seen.has(pendingKey(item)));
}

/**
 * Adds a bell notification once per newly pending thread. The first successful load only seeds
 * what is already waiting; the shared pending-approvals query refreshes on its own interval.
 */
export function useApprovalNotifications() {
  const { data } = usePendingApprovals();
  const seen = useRef<Set<string> | null>(null);

  useEffect(() => {
    if (!data) return;
    if (seen.current === null) {
      seen.current = new Set(data.map(pendingKey));
      return;
    }
    for (const item of unseenPending(seen.current, data)) {
      seen.current.add(pendingKey(item));
      notifyApprovalNeeded(item);
    }
  }, [data]);
}
