import { useThread } from '@/entities/thread';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';

interface ThreadStateSummaryProps {
  threadId: string;
}

function cell(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** Current run status, rolling summary and the approvals audit trail of a thread. */
export function ThreadStateSummary({ threadId }: ThreadStateSummaryProps) {
  const { data: thread, isLoading, isError } = useThread(threadId);

  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (isError || !thread) {
    return <p className="text-destructive text-sm">Could not load the thread state.</p>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          Current state <Badge variant="secondary">{thread.run.status}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {thread.run.error && <p className="text-destructive">{thread.run.error}</p>}
        <p>{thread.summary ?? <span className="text-muted-foreground">No summary yet.</span>}</p>
        {thread.approvals.length === 0 ? (
          <p className="text-muted-foreground">No approvals recorded.</p>
        ) : (
          <table className="w-full text-left" aria-label="Approvals audit trail">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 pr-3">Action</th>
                <th className="py-1 pr-3">Tool</th>
                <th className="py-1">Decision</th>
              </tr>
            </thead>
            <tbody>
              {thread.approvals.map((entry, index) => (
                <tr key={`${cell(entry.action_id)}-${String(index)}`} className="border-t">
                  <td className="py-1 pr-3 font-mono">{cell(entry.action_id)}</td>
                  <td className="py-1 pr-3">{cell(entry.tool_name)}</td>
                  <td className="py-1">{cell(entry.decision)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}
