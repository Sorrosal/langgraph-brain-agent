import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePrefersReducedMotion } from '@/shared/hooks/use-prefers-reduced-motion';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';
import { Card } from '@/shared/ui/card';
import { AUTOPLAY_INTERVAL_MS, CRASH_STEPS } from '../model/steps';

const LAST_INDEX = CRASH_STEPS.length - 1;

export function CrashWalkthrough() {
  const { t } = useTranslation('landing');
  const reducedMotion = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);
  const [autoplayRequested, setAutoplayRequested] = useState(false);
  const autoplay = autoplayRequested && !reducedMotion;
  const stepId = CRASH_STEPS[index] ?? CRASH_STEPS[0];

  useEffect(() => {
    if (!autoplay) return;
    const timer = window.setInterval(() => {
      setIndex((current) => (current >= LAST_INDEX ? 0 : current + 1));
    }, AUTOPLAY_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [autoplay]);

  return (
    <Card className="p-5 sm:p-6">
      <ol className="flex items-start" aria-label={t('crashWalkthrough.timelineLabel')}>
        {CRASH_STEPS.map((id, position) => {
          const label = t(`crashWalkthrough.steps.${id}.label`);
          return (
            <li
              key={id}
              aria-current={position === index ? 'step' : undefined}
              className="flex flex-1 flex-col items-center gap-2 text-center"
            >
              <button
                type="button"
                onClick={() => {
                  setIndex(position);
                }}
                aria-label={t('crashWalkthrough.stepLabel', { number: position + 1, label })}
                className={cn(
                  'focus-visible:ring-ring flex size-11 items-center justify-center rounded-full border text-sm font-semibold transition-colors duration-200 outline-none focus-visible:ring-2 motion-reduce:transition-none sm:size-9',
                  position === index
                    ? 'bg-primary text-primary-foreground border-primary shadow-primary'
                    : position < index
                      ? 'bg-brand-bg text-brand-ink border-transparent'
                      : 'bg-subtle text-muted-foreground border-input hover:bg-accent',
                )}
              >
                {position + 1}
              </button>
              <span
                className={cn(
                  'hidden text-xs sm:block',
                  position === index ? 'text-foreground font-semibold' : 'text-muted-foreground',
                )}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>
      <div className="mt-6 min-h-52 sm:min-h-40" aria-live={autoplay ? 'off' : 'polite'}>
        <p className="text-brand-ink text-2xs font-semibold tracking-wide uppercase">
          {t('crashWalkthrough.stepOf', { current: index + 1, total: CRASH_STEPS.length })}
        </p>
        <h3 className="mt-1 text-lg font-semibold">
          {t(`crashWalkthrough.steps.${stepId}.title`)}
        </h3>
        <p className="text-muted-foreground mt-2 text-sm">
          {t(`crashWalkthrough.steps.${stepId}.description`)}
        </p>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          className="max-sm:h-11"
          size="sm"
          onClick={() => {
            setIndex((current) => Math.max(current - 1, 0));
          }}
          disabled={index === 0}
        >
          <ChevronLeft aria-hidden="true" />
          {t('crashWalkthrough.prev')}
        </Button>
        <Button
          variant="outline"
          className="max-sm:h-11"
          size="sm"
          onClick={() => {
            setIndex((current) => Math.min(current + 1, LAST_INDEX));
          }}
          disabled={index === LAST_INDEX}
        >
          {t('crashWalkthrough.next')}
          <ChevronRight aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          className="max-sm:h-11"
          size="sm"
          onClick={() => {
            setAutoplayRequested((current) => !current);
          }}
          disabled={reducedMotion}
          aria-pressed={autoplay}
          title={reducedMotion ? t('crashWalkthrough.autoplayDisabled') : undefined}
        >
          {autoplay ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
          {t('crashWalkthrough.autoplay')}
        </Button>
      </div>
    </Card>
  );
}
