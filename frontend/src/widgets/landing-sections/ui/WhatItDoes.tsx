import { Ban, ListChecks, Mail, ShieldCheck, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Card } from '@/shared/ui/card';
import { Section } from '@/shared/ui/section';
import { BLOCKED, NEEDS_APPROVAL, USE_CASES } from '../model/what-it-does';

const USE_CASE_ICONS = { email: Mail, crm: Users, tasks: ListChecks } as const;

export function WhatItDoes() {
  const { t } = useTranslation('landing');

  return (
    <Section
      id="what-it-does"
      title={t('whatItDoes.title')}
      description={t('whatItDoes.description')}
    >
      <ul className="grid gap-4 sm:grid-cols-3">
        {USE_CASES.map((id) => {
          const Icon = USE_CASE_ICONS[id];
          return (
            <li key={id}>
              <Card className="h-full p-5">
                <span className="bg-brand-bg text-brand-ink flex size-9 items-center justify-center rounded-[var(--radius-md)]">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                <h3 className="mt-4 font-semibold">{t(`whatItDoes.useCases.${id}.title`)}</h3>
                <p className="text-muted-foreground mt-2 text-sm">
                  {t(`whatItDoes.useCases.${id}.text`)}
                </p>
              </Card>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <h3 className="flex items-center gap-2.5 font-semibold">
            <span className="bg-warning-bg text-warning-fg flex size-8 items-center justify-center rounded-full">
              <ShieldCheck className="size-4" aria-hidden="true" />
            </span>
            {t('whatItDoes.needsApproval.title')}
          </h3>
          <ul className="text-muted-foreground marker:text-faint mt-4 list-disc space-y-1.5 pl-5 text-sm">
            {NEEDS_APPROVAL.map((id) => (
              <li key={id}>{t(`whatItDoes.needsApproval.items.${id}`)}</li>
            ))}
          </ul>
        </Card>
        <Card className="p-5">
          <h3 className="flex items-center gap-2.5 font-semibold">
            <span className="bg-danger-bg text-danger-fg flex size-8 items-center justify-center rounded-full">
              <Ban className="size-4" aria-hidden="true" />
            </span>
            {t('whatItDoes.blocked.title')}
          </h3>
          <ul className="text-muted-foreground marker:text-faint mt-4 list-disc space-y-1.5 pl-5 text-sm">
            {BLOCKED.map((id) => (
              <li key={id}>{t(`whatItDoes.blocked.items.${id}`)}</li>
            ))}
          </ul>
        </Card>
      </div>
    </Section>
  );
}
