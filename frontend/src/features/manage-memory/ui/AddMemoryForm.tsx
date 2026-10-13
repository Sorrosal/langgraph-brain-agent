import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, Plus } from 'lucide-react';
import { useId } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { memoryKindSchema } from '@/entities/memory';
import { Button } from '@/shared/ui/button';
import { Card, CardContent } from '@/shared/ui/card';
import { Textarea } from '@/shared/ui/textarea';
import { useAddMemory } from '../api/manage-memory.api';
import { addMemorySchema } from '../model/memory-form.schemas';
import type { AddMemoryValues } from '../model/memory-form.schemas';

export function AddMemoryForm() {
  const { t } = useTranslation('brain');
  const errorId = useId();
  const { mutate: addMemory, isPending } = useAddMemory();
  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<AddMemoryValues>({
    resolver: zodResolver(addMemorySchema),
    defaultValues: { kind: 'fact', text: '' },
  });
  const kind = watch('kind');

  function onSubmit(values: AddMemoryValues) {
    addMemory(values, {
      onSuccess: () => {
        reset({ kind: values.kind, text: '' });
      },
    });
  }

  return (
    <Card>
      <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} noValidate>
        <CardContent className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="flex flex-col gap-0.5">
            <h2 className="text-base font-semibold">{t('memories.add.title')}</h2>
            <p className="text-muted-foreground text-sm">{t('memories.add.description')}</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <div
              role="radiogroup"
              aria-label={t('memories.add.kindLabel')}
              className="bg-muted inline-flex w-fit max-w-full gap-1 overflow-x-auto rounded-[var(--radius-md)] p-1"
            >
              {memoryKindSchema.options.map((option) => (
                <label key={option} className="relative">
                  <input
                    type="radio"
                    value={option}
                    className="peer sr-only"
                    {...register('kind')}
                  />
                  <span className="text-muted-foreground hover:text-foreground peer-checked:bg-elevated peer-checked:text-foreground peer-checked:shadow-e1 peer-focus-visible:ring-ring flex min-h-11 cursor-pointer items-center rounded-[var(--radius-sm)] px-3.5 text-sm font-medium whitespace-nowrap transition-colors peer-focus-visible:ring-2 sm:min-h-9">
                    {t(`kinds.${option}`)}
                  </span>
                </label>
              ))}
            </div>
            <p className="text-muted-foreground text-xs">{t(`kindHints.${kind}`)}</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Textarea
              rows={3}
              aria-label={t('memories.add.textLabel')}
              placeholder={t('memories.add.placeholder')}
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
              {t('memories.add.submit')}
            </Button>
          </div>
        </CardContent>
      </form>
    </Card>
  );
}
