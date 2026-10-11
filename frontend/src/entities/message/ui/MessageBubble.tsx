import { Wrench } from 'lucide-react';
import { cn } from '@/shared/lib/cn';
import { truncate } from '@/shared/lib/format';
import type { Message, ToolCall } from '../model/message.types';

interface MessageBubbleProps {
  message: Message;
  className?: string;
}

const ARGS_PREVIEW_LENGTH = 120;

function ToolCallCard({ call }: { call: ToolCall }) {
  const args = JSON.stringify(call.args);
  return (
    <div className="bg-background/60 flex items-center gap-2 rounded-md border px-2 py-1 text-xs">
      <Wrench className="h-3 w-3 shrink-0" aria-hidden="true" />
      <code className="font-semibold">{call.name}</code>
      <code className="text-muted-foreground truncate" title={args}>
        {truncate(args, ARGS_PREVIEW_LENGTH)}
      </code>
    </div>
  );
}

export function MessageBubble({ message, className }: MessageBubbleProps) {
  if (message.role === 'tool') {
    return (
      <details
        className={cn('bg-muted/50 max-w-[85%] self-start rounded-lg border px-3 py-2', className)}
      >
        <summary className="cursor-pointer text-xs font-medium">
          Tool result{message.status === 'error' ? ' (error)' : ''}
        </summary>
        <pre className="mt-2 max-h-64 overflow-auto font-mono text-xs whitespace-pre-wrap">
          {message.content}
        </pre>
      </details>
    );
  }

  const isHuman = message.role === 'human';
  return (
    <article
      aria-label={isHuman ? 'You' : 'Assistant'}
      className={cn(
        'flex max-w-[85%] flex-col gap-2 rounded-lg px-3 py-2 text-sm',
        isHuman ? 'bg-primary text-primary-foreground self-end' : 'bg-muted self-start',
        className,
      )}
    >
      {message.content && <p className="break-words whitespace-pre-wrap">{message.content}</p>}
      {message.tool_calls.map((call, index) => (
        <ToolCallCard key={call.id ?? index} call={call} />
      ))}
    </article>
  );
}
