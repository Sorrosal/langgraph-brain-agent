import { ShieldAlert, Scissors, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useThread } from '@/entities/thread';
import { formatNumber } from '@/shared/lib/format';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card';
import { cn } from '@/shared/lib/cn';

interface ContextReportProps {
  threadId: string;
}

/** What the agent's last model call was given: stable prompt, history and turn context. */
export function ContextReport({ threadId }: ContextReportProps) {
  const { t } = useTranslation('inspector');
  const { data } = useThread(threadId);
  const report = data?.context_report;

  if (!data) return null;
  if (!report) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t('context.title')}</CardTitle>
          <CardDescription>{t('context.empty')}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const parts = [
    {
      key: 'system',
      tokens: report.system_tokens,
      hint: t('context.systemHint'),
      color: 'bg-brand',
    },
    {
      key: 'history',
      tokens: report.history_tokens,
      hint: t('context.historyHint', { count: report.history_messages }),
      color: 'bg-info',
    },
    {
      key: 'turn',
      tokens: report.turn_context_tokens,
      hint: t('context.turnHint'),
      color: 'bg-success',
    },
  ] as const;
  const cached = report.cached_tokens ?? 0;
  const total = Math.max(
    parts.reduce((sum, part) => sum + part.tokens, 0),
    1,
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('context.title')}</CardTitle>
        <CardDescription>{t('context.subtitle', { step: report.step })}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="bg-muted flex h-2.5 overflow-hidden rounded-full" aria-hidden="true">
          {parts.map((part) => (
            <span
              key={part.key}
              className={cn('h-full', part.color)}
              style={{ width: `${String((part.tokens / total) * 100)}%` }}
            />
          ))}
        </div>
        <dl className="grid gap-3 sm:grid-cols-3">
          {parts.map((part) => (
            <div key={part.key} className="flex gap-2.5">
              <span
                className={cn('mt-1.5 size-2.5 shrink-0 rounded-full', part.color)}
                aria-hidden="true"
              />
              <div className="flex flex-col">
                <dt className="text-sm font-medium">{t(`context.${part.key}`)}</dt>
                <dd className="text-muted-foreground text-xs">
                  {t('context.tokens', { count: part.tokens })} · {part.hint}
                </dd>
              </div>
            </div>
          ))}
        </dl>
        {report.input_tokens != null && (
          <div className="flex flex-col gap-1">
            <Badge variant={cached > 0 ? 'success' : 'secondary'} className="w-fit">
              <Zap className="size-3" aria-hidden="true" />
              {t('context.usage', {
                input: formatNumber(report.input_tokens),
                cached: formatNumber(cached),
                percent: formatNumber(report.input_tokens > 0 ? cached / report.input_tokens : 0, {
                  style: 'percent',
                  maximumFractionDigits: 0,
                }),
              })}
            </Badge>
            <p className="text-muted-foreground text-xs">{t('context.usageHint')}</p>
          </div>
        )}
        {(report.cleared_tool_results > 0 || report.untrusted_in_context) && (
          <div className="flex flex-wrap gap-2">
            {report.cleared_tool_results > 0 && (
              <Badge variant="info">
                <Scissors className="size-3" aria-hidden="true" />
                {t('context.cleared', { count: report.cleared_tool_results })}
              </Badge>
            )}
            {report.untrusted_in_context && (
              <Badge variant="warning">
                <ShieldAlert className="size-3" aria-hidden="true" />
                {t('context.untrusted')}
              </Badge>
            )}
          </div>
        )}
        {report.turn_context && (
          <details className="group">
            <summary className="text-brand-ink cursor-pointer text-sm font-medium select-none">
              {t('context.showTurn')}
            </summary>
            <pre className="bg-subtle mt-2 max-h-80 overflow-auto rounded-[var(--radius-md)] border p-3 font-mono text-xs whitespace-pre-wrap">
              {report.turn_context}
            </pre>
          </details>
        )}
      </CardContent>
    </Card>
  );
}
