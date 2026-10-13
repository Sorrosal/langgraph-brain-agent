import { AlertCircle, Info, RotateCw, Sparkles } from 'lucide-react';
import { Trans, useTranslation } from 'react-i18next';
import { RuleCard, useRules } from '@/entities/rule';
import { RuleFileEditor } from '@/features/edit-rules';
import { selectIsAdmin, useAuthStore } from '@/features/auth';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { Card, CardContent } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';

interface RulesSectionProps {
  id: string;
  title: string;
  description: string;
  children: React.ReactNode;
}

function RulesSection({ id, title, description, children }: RulesSectionProps) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 id={id} className="text-base font-semibold">
          {title}
        </h2>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>
      {children}
    </section>
  );
}

function RulesSkeleton({ label }: { label: string }) {
  return (
    <div className="flex flex-col gap-8" role="status" aria-busy="true">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-5 w-56" />
      <div className="flex flex-col gap-3">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-20 w-full rounded-[var(--radius-lg)]" />
      </div>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-32 w-full rounded-[var(--radius-lg)]" />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Skeleton className="h-32 rounded-[var(--radius-lg)]" />
        <Skeleton className="h-32 rounded-[var(--radius-lg)]" />
      </div>
    </div>
  );
}

export function BrainRules() {
  const { t } = useTranslation('brain');
  const isAdmin = useAuthStore(selectIsAdmin);
  const { data: rules, isLoading, isError, refetch } = useRules();

  if (isLoading) return <RulesSkeleton label={t('common:actions.loading')} />;
  if (isError || !rules) {
    return (
      <div
        role="alert"
        className="bg-card/60 flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border border-dashed px-6 py-10 text-center"
      >
        <span className="bg-danger-bg text-danger-fg flex size-11 items-center justify-center rounded-full">
          <AlertCircle className="size-5" aria-hidden />
        </span>
        <p className="font-medium">{t('rules.loadError')}</p>
        <Button
          variant="outline"
          onClick={() => {
            void refetch();
          }}
        >
          <RotateCw aria-hidden />
          {t('common:actions.retry')}
        </Button>
      </div>
    );
  }

  const guidelines = [...rules.guidelines].sort((a, b) => b.priority - a.priority);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">{t('rules.version')}</span>
        <code className="bg-muted rounded-sm px-1.5 py-0.5 font-mono text-xs">
          {rules.version_hash}
        </code>
      </div>

      <RulesSection
        id="rules-persona"
        title={t('rules.persona.title')}
        description={t('rules.persona.description')}
      >
        <Card className="overflow-hidden">
          <CardContent className="border-brand border-l-2 p-4 text-sm whitespace-pre-wrap">
            {rules.persona ?? (
              <span className="text-muted-foreground">{t('rules.persona.empty')}</span>
            )}
          </CardContent>
        </Card>
      </RulesSection>

      <RulesSection
        id="rules-guidelines"
        title={t('rules.guidelines.title')}
        description={t('rules.guidelines.description')}
      >
        {guidelines.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t('rules.guidelines.empty')}</p>
        ) : (
          <Card>
            <ul className="divide-y">
              {guidelines.map((guideline) => (
                <li key={guideline.id} className="flex items-start gap-3 p-3.5 text-sm">
                  <Badge
                    variant="secondary"
                    className="mt-0.5 tabular-nums"
                    title={t('rules.guidelines.priority', { priority: guideline.priority })}
                  >
                    {t('rules.guidelines.priorityShort', { priority: guideline.priority })}
                  </Badge>
                  <span>{guideline.text}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </RulesSection>

      <RulesSection
        id="rules-hard"
        title={t('rules.hardRules.title')}
        description={t('rules.hardRules.description')}
      >
        {rules.hard_rules.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t('rules.hardRules.empty')}</p>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {rules.hard_rules.map((rule) => (
              <li key={rule.id}>
                <RuleCard rule={rule} />
              </li>
            ))}
          </ul>
        )}
      </RulesSection>

      <RulesSection
        id="rules-files"
        title={t('rules.files.title')}
        description={t('rules.files.description')}
      >
        <div className="border-info-border bg-info-bg text-info-fg flex items-start gap-2.5 rounded-[var(--radius-md)] border p-3 text-sm">
          {isAdmin ? (
            <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
          ) : (
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          )}
          <p>
            {isAdmin ? (
              <Trans
                t={t}
                i18nKey="rules.files.chatHint"
                components={{ code: <code className="font-mono text-xs font-semibold" /> }}
              />
            ) : (
              t('rules.readOnlyNote')
            )}
          </p>
        </div>
        {rules.files.map((file) => (
          // remount when the server content changes (after a save) to reset the draft
          <RuleFileEditor
            key={`${file.name}:${rules.version_hash}`}
            name={file.name}
            content={file.content}
            readOnly={!isAdmin}
          />
        ))}
      </RulesSection>
    </div>
  );
}
