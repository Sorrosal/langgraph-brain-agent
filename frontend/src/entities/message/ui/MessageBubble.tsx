import { CircleAlert, CircleCheck, Wrench } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/shared/lib/cn';
import { truncate } from '@/shared/lib/format';
import type { Message, ToolCall } from '../model/message.types';

interface MessageBubbleProps {
  message: Message;
  className?: string;
}

const ARGS_PREVIEW_LENGTH = 120;

/** The assistant's mark: the prism orb, the only place the AI signature appears in a thread. */
export function AssistantMark({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cn('ev-orb block size-7 shrink-0', className)} />;
}

/** Assistant text: GitHub-flavoured markdown, links open in a new tab. */
export function AssistantText({ text }: { text: string }) {
  return (
    <div className="ev-prose text-reading">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
          // Wide tables scroll inside the message instead of stretching the thread.
          table: ({ node: _node, ...props }) => (
            <div className="max-w-full overflow-x-auto">
              <table {...props} />
            </div>
          ),
        }}
      >
        {text}
      </Markdown>
    </div>
  );
}

export function ToolCallCard({ call }: { call: ToolCall }) {
  const { t } = useTranslation();
  const args = JSON.stringify(call.args);
  const label = t(`tools.${call.name}`, { defaultValue: call.name });
  return (
    <div className="bg-subtle flex max-w-full min-w-0 items-center gap-2 rounded-[var(--radius-md)] border px-2.5 py-1.5 text-xs">
      <Wrench className="text-brand-ink size-3.5 shrink-0" aria-hidden="true" />
      <span className="font-medium whitespace-nowrap">{label}</span>
      {label !== call.name && <code className="text-faint font-mono">{call.name}</code>}
      <code className="text-muted-foreground min-w-0 truncate font-mono" title={args}>
        {truncate(args, ARGS_PREVIEW_LENGTH)}
      </code>
    </div>
  );
}

export function MessageBubble({ message, className }: MessageBubbleProps) {
  const { t } = useTranslation('chat');

  if (message.role === 'tool') {
    const failed = message.status === 'error';
    const Icon = failed ? CircleAlert : CircleCheck;
    return (
      <details
        data-message
        className={cn('group ml-10 max-w-[min(85%,42rem)] self-start text-xs', className)}
      >
        <summary className="text-muted-foreground hover:text-foreground inline-flex cursor-pointer items-center gap-1.5 rounded-[var(--radius-sm)] px-1.5 py-1 font-medium select-none">
          <Icon
            className={cn('size-3.5', failed ? 'text-danger' : 'text-success')}
            aria-hidden="true"
          />
          {failed ? t('tool.resultError') : t('tool.result')}
        </summary>
        <pre className="bg-subtle mt-1.5 max-h-64 overflow-auto rounded-[var(--radius-md)] border p-3 font-mono text-xs whitespace-pre-wrap">
          {message.content}
        </pre>
      </details>
    );
  }

  if (message.role === 'human') {
    return (
      <article
        data-message
        aria-label={t('you')}
        className={cn(
          'bg-chat-user text-foreground text-reading max-w-[min(85%,42rem)] self-end rounded-[var(--radius-xl)] rounded-br-[6px] px-4 py-2.5',
          className,
        )}
      >
        <p className="break-words whitespace-pre-wrap">{message.content}</p>
      </article>
    );
  }

  return (
    <article
      data-message
      aria-label={t('assistant')}
      className={cn('flex max-w-[min(100%,48rem)] min-w-0 gap-3 self-start', className)}
    >
      <AssistantMark className="mt-0.5" />
      <div className="flex min-w-0 flex-col gap-2 pt-0.5">
        {message.content && <AssistantText text={message.content} />}
        {message.tool_calls.map((call, index) => (
          <ToolCallCard key={call.id ?? index} call={call} />
        ))}
      </div>
    </article>
  );
}
