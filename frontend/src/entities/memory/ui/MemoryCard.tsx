import { MessageSquare } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent } from '@/shared/ui/card';
import { formatDate, formatNumber, formatRelativeTime } from '@/shared/lib/format';
import type { Memory, MemoryKind } from '../model/memory.schemas';

const KIND_VARIANT = {
  fact: 'info',
  preference: 'default',
  episode: 'warning',
} as const satisfies Record<MemoryKind, 'info' | 'default' | 'warning'>;

interface MemoryCardProps {
  memory: Memory;
  /** Slot for feature actions (e.g. delete). */
  actions?: React.ReactNode;
}

export function MemoryCard({ memory, actions }: MemoryCardProps) {
  const { t } = useTranslation('brain');

  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Badge variant={KIND_VARIANT[memory.kind]}>{t(`kinds.${memory.kind}`)}</Badge>
            {memory.score !== null && (
              <span className="text-muted-foreground text-xs tabular-nums">
                {t('memories.card.match', {
                  score: formatNumber(memory.score, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  }),
                })}
              </span>
            )}
            <time
              dateTime={memory.created_at}
              title={t('memories.card.createdAt', {
                date: formatDate(memory.created_at, { dateStyle: 'medium', timeStyle: 'short' }),
              })}
              className="text-muted-foreground text-xs"
            >
              {formatRelativeTime(memory.created_at)}
            </time>
            {memory.source_thread_id && (
              <Link
                to={`/app/chat/${encodeURIComponent(memory.source_thread_id)}`}
                className="text-brand-ink inline-flex items-center gap-1 rounded-sm text-xs hover:underline"
              >
                <MessageSquare className="size-3" aria-hidden />
                {t('memories.card.fromChat')}
              </Link>
            )}
          </div>
          <p className="text-reading break-words whitespace-pre-wrap">{memory.text}</p>
        </div>
        {actions}
      </CardContent>
    </Card>
  );
}
