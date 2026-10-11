import { Badge } from '@/shared/ui/badge';
import { Card, CardContent } from '@/shared/ui/card';
import type { HardRule } from '../model/rule.schemas';

interface RuleCardProps {
  rule: HardRule;
}

export function RuleCard({ rule }: RuleCardProps) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-medium">{rule.id}</span>
          <Badge variant={rule.action === 'block' ? 'destructive' : 'secondary'}>
            {rule.action}
          </Badge>
          <Badge variant="outline">risk: {rule.risk}</Badge>
        </div>
        <p className="text-sm">{rule.description}</p>
        <p className="text-muted-foreground text-xs">
          tool: <code className="font-mono">{rule.when.tool}</code>
        </p>
      </CardContent>
    </Card>
  );
}
