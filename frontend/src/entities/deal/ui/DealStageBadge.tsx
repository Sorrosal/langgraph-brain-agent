import { useTranslation } from 'react-i18next';
import { Badge } from '@/shared/ui/badge';
import type { DealStage } from '../model/deal.schemas';

const VARIANT = {
  lead: 'secondary',
  qualified: 'info',
  proposal: 'default',
  won: 'success',
  lost: 'destructive',
} as const satisfies Record<DealStage, string>;

export function DealStageBadge({ stage }: { stage: DealStage }) {
  const { t } = useTranslation('data');
  return <Badge variant={VARIANT[stage]}>{t(`deals.stages.${stage}`)}</Badge>;
}
