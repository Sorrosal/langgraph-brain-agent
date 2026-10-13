import { useTranslation } from 'react-i18next';
import { Badge } from '@/shared/ui/badge';
import type { ActionRequest } from '../model/approval.types';

const RISK_VARIANT = { low: 'info', medium: 'warning', high: 'destructive' } as const;

export function RiskBadge({
  risk,
  className,
}: {
  risk: ActionRequest['risk'];
  className?: string;
}) {
  const { t } = useTranslation('approvals');
  return (
    <Badge variant={RISK_VARIANT[risk]} className={className}>
      {t(`risk.${risk}`)}
    </Badge>
  );
}
