import { useTranslation } from 'react-i18next';
import { Badge } from '@/shared/ui/badge';
import { Card } from '@/shared/ui/card';
import { Section } from '@/shared/ui/section';
import { HITL_DECISIONS, HITL_LIFECYCLE, HITL_NOTES, UNCERTAIN_OPTIONS } from '../model/hitl';

export function HumanInTheLoop() {
  const { t } = useTranslation('landing');

  return (
    <Section id="human-in-the-loop" title={t('hitl.title')} description={t('hitl.description')}>
      <ol className="grid gap-4 md:grid-cols-3">
        {HITL_LIFECYCLE.map((id, index) => (
          <li key={id}>
            <Card className="h-full p-5">
              <p className="text-brand-ink text-2xs font-semibold tracking-wide uppercase">
                {t('hitl.step', { number: index + 1 })}
              </p>
              <h3 className="mt-1 font-semibold">{t(`hitl.lifecycle.${id}.label`)}</h3>
              <p className="text-muted-foreground mt-2 text-sm">{t(`hitl.lifecycle.${id}.text`)}</p>
              {id === 'decision' && (
                <ul className="mt-3 flex flex-wrap gap-2" aria-label={t('hitl.decisionsLabel')}>
                  {HITL_DECISIONS.map((decision) => (
                    <li key={decision}>
                      <Badge variant="outline">{t(`hitl.decisions.${decision}`)}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </li>
        ))}
      </ol>
      <ul className="text-muted-foreground marker:text-faint mt-6 list-disc space-y-1.5 pl-5 text-sm">
        {HITL_NOTES.map((note) => (
          <li key={note}>{t(`hitl.notes.${note}`)}</li>
        ))}
      </ul>
      <h3 className="mt-10 font-semibold">{t('hitl.uncertainTitle')}</h3>
      <ul className="mt-3 grid gap-4 md:grid-cols-3">
        {UNCERTAIN_OPTIONS.map((id) => (
          <li key={id}>
            <Card className="h-full p-4">
              <p className="font-medium">{t(`hitl.uncertain.${id}.label`)}</p>
              <p className="text-muted-foreground mt-1 text-sm">{t(`hitl.uncertain.${id}.text`)}</p>
            </Card>
          </li>
        ))}
      </ul>
    </Section>
  );
}
