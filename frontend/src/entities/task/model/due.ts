import { formatDate } from '@/shared/lib/format';
import type { Task } from './task.schemas';

const DAY_MS = 86_400_000;
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** A bare `YYYY-MM-DD` is a calendar day: format it in UTC so it never shifts to the day before. */
export function formatDueDate(due: string): string {
  return formatDate(due, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...(DATE_ONLY.test(due) && { timeZone: 'UTC' }),
  });
}

/** Open tasks whose due day (or instant) has passed. */
export function isOverdue(task: Pick<Task, 'status' | 'due_date'>, now = Date.now()): boolean {
  if (task.status === 'done' || !task.due_date) return false;
  const due = new Date(task.due_date).getTime();
  return (DATE_ONLY.test(task.due_date) ? due + DAY_MS : due) < now;
}
