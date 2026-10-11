import type { ReactNode } from 'react';
import { Badge } from '@/shared/ui/badge';
import { cn } from '@/shared/lib/cn';
import type { ActionRequest, UncertainAction } from '../model/approval.types';

interface ActionCardProps {
  action: ActionRequest | UncertainAction;
  children?: ReactNode;
  className?: string;
}

const riskStyles = {
  low: 'secondary',
  medium: 'outline',
  high: 'destructive',
} as const;

export function ActionCard({ action, children, className }: ActionCardProps) {
  const explanation = 'reason' in action ? action.reason : action.message;

  return (
    <section
      aria-label={`Action ${action.tool_name}`}
      className={cn('bg-card flex flex-col gap-2 rounded-lg border p-3', className)}
    >
      <header className="flex flex-wrap items-center gap-2">
        <code className="font-mono text-sm font-semibold">{action.tool_name}</code>
        {'risk' in action && <Badge variant={riskStyles[action.risk]}>{action.risk} risk</Badge>}
      </header>
      <p className="text-muted-foreground text-sm">{explanation}</p>
      <pre className="bg-muted max-h-48 overflow-auto rounded-md p-2 font-mono text-xs">
        {JSON.stringify(action.args, null, 2)}
      </pre>
      {children}
    </section>
  );
}
