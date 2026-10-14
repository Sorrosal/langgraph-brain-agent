import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, Plus } from 'lucide-react';
import { useId } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/shared/ui/button';
import { Card, CardContent } from '@/shared/ui/card';
import { Textarea } from '@/shared/ui/textarea';
import { useAddOrgKnowledge } from '../api/manage-org-knowledge.api';
import { addOrgKnowledgeSchema } from '../model/org-knowledge-form.schemas';
import type { AddOrgKnowledgeValues } from '../model/org-knowledge-form.schemas';

/** Admin-only form; the backend rejects anyone else with 403. */
export function AddOrgKnowledgeForm() {
  const { t } = useTranslation('brain');
  const errorId = useId();
  const { mutate: add, isPending } = useAddOrgKnowledge();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AddOrgKnowledgeValues>({
    resolver: zodResolver(addOrgKnowledgeSchema),
    defaultValues: { text: '' },
  });

  function onSubmit(values: AddOrgKnowledgeValues) {
    add(values, {
      onSuccess: () => {
        reset({ text: '' });
      },
    });
  }

  return (
    <Card>
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate>
        <CardContent className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="flex flex-col gap-0.5">
            <h2 className="text-base font-semibold">{t('org.add.title')}</h2>
            <p className="text-muted-foreground text-sm">{t('org.add.description')}</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Textarea
              rows={3}
              aria-label={t('org.add.textLabel')}
              placeholder={t('org.add.placeholder')}
              aria-invalid={Boolean(errors.text)}
              aria-describedby={errors.text ? errorId : undefined}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter')
                  e.currentTarget.form?.requestSubmit();
              }}
              {...register('text')}
            />
            {errors.text && (
              <p id={errorId} role="alert" className="text-danger-fg text-sm">
                {errors.text.message}
              </p>
            )}
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={isPending} className="h-11 w-full sm:h-10 sm:w-auto">
              {isPending ? (
                <Loader2 className="motion-safe:animate-spin" aria-hidden />
              ) : (
                <Plus aria-hidden />
              )}
              {t('org.add.submit')}
            </Button>
          </div>
        </CardContent>
      </form>
    </Card>
  );
}
