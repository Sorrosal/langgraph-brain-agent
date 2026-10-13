import { useTranslation } from 'react-i18next';
import { Badge } from '@/shared/ui/badge';
import type { Task, TaskStatus } from '../model/task.schemas';

const STATUS_VARIANT = { open: 'info', done: 'success' } as const satisfies Record<
  TaskStatus,
  string
>;

const PRIORITY_VARIANT = {
  low: 'outline',
  normal: 'secondary',
  high: 'warning',
} as const satisfies Record<Task['priority'], string>;

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const { t } = useTranslation('data');
  return <Badge variant={STATUS_VARIANT[status]}>{t(`tasks.statuses.${status}`)}</Badge>;
}

export function TaskPriorityBadge({ priority }: { priority: Task['priority'] }) {
  const { t } = useTranslation('data');
  return <Badge variant={PRIORITY_VARIANT[priority]}>{t(`tasks.priorities.${priority}`)}</Badge>;
}
