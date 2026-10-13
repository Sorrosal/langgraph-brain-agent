import { Brain as BrainIcon, Gauge, ScrollText } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/shared/ui/card';
import { Section } from '@/shared/ui/section';
import { BRAIN_CARDS } from '../model/brain';

const CARD_ICONS = { memory: BrainIcon, rules: ScrollText, budget: Gauge } as const;

export function Brain() {
  const { t } = useTranslation('landing');

  return (
    <Section id="brain" title={t('brain.title')} description={t('brain.description')}>
      <div className="grid gap-4 md:grid-cols-3">
        {BRAIN_CARDS.map(({ id, items }) => {
          const Icon = CARD_ICONS[id];
          return (
            <Card key={id} className="p-5">
              <span className="bg-brand-bg text-brand-ink flex size-9 items-center justify-center rounded-[var(--radius-md)]">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <h3 className="mt-4 font-semibold">{t(`brain.cards.${id}.title`)}</h3>
              <ul className="text-muted-foreground marker:text-faint mt-3 list-disc space-y-1.5 pl-5 text-sm">
                {items.map((item) => (
                  <li key={item}>{t(`brain.cards.${id}.items.${item}`)}</li>
                ))}
              </ul>
            </Card>
          );
        })}
      </div>
    </Section>
  );
}
