import { Badge } from '@/shared/ui/badge';
import { Card, CardContent } from '@/shared/ui/card';
import { formatRelativeTime } from '@/shared/lib/format';
import type { Memory } from '../model/memory.schemas';

interface MemoryCardProps {
  memory: Memory;
  /** Slot for feature actions (e.g. delete). */
  actions?: React.ReactNode;
}

export function MemoryCard({ memory, actions }: MemoryCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{memory.kind}</Badge>
            {memory.score !== null && (
              <span className="text-muted-foreground text-xs">match {memory.score.toFixed(2)}</span>
            )}
            <span className="text-muted-foreground text-xs">
              {formatRelativeTime(memory.created_at)}
            </span>
          </div>
          <p className="text-sm break-words">{memory.text}</p>
        </div>
        {actions}
      </CardContent>
    </Card>
  );
}
