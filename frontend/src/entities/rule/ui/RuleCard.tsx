import { Ban, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent } from '@/shared/ui/card';
import type { HardRule } from '../model/rule.schemas';

interface RuleCardProps {
  rule: HardRule;
}

export function RuleCard({ rule }: RuleCardProps) {
  const { t } = useTranslation('brain');
  const blocked = rule.action === 'block';
  const ActionIcon = blocked ? Ban : ShieldCheck;

  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={blocked ? 'destructive' : 'warning'}>
            <ActionIcon className="size-3" aria-hidden />
            {t(`rules.hardRules.actions.${rule.action}`)}
          </Badge>
          <Badge variant="outline">
            {t('rules.hardRules.risk', { level: t(`rules.hardRules.levels.${rule.risk}`) })}
          </Badge>
        </div>
        <div className="flex flex-col gap-1">
          <p className="font-mono text-sm font-medium break-all">{rule.id}</p>
          <p className="text-sm">{rule.description}</p>
        </div>
        {rule.reason && (
          <p className="text-muted-foreground text-xs">
            <span className="font-medium">{t('rules.hardRules.reason')}:</span> {rule.reason}
          </p>
        )}
        <p className="text-muted-foreground mt-auto text-xs">
          {t('rules.hardRules.tool')}:{' '}
          <code className="bg-muted rounded-sm px-1 py-0.5 font-mono">{rule.when.tool}</code>
        </p>
      </CardContent>
    </Card>
  );
}
