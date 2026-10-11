import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react';
import { useEffect, useState } from 'react';
import { usePrefersReducedMotion } from '@/shared/hooks/use-prefers-reduced-motion';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';
import { AUTOPLAY_INTERVAL_MS, CRASH_STEPS } from '../model/steps';

const LAST_INDEX = CRASH_STEPS.length - 1;

export function CrashWalkthrough() {
  const reducedMotion = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);
  const [autoplayRequested, setAutoplayRequested] = useState(false);
  const autoplay = autoplayRequested && !reducedMotion;
  const step = CRASH_STEPS[index] ?? CRASH_STEPS[0];

  useEffect(() => {
    if (!autoplay) return;
    const timer = window.setInterval(() => {
      setIndex((current) => (current >= LAST_INDEX ? 0 : current + 1));
    }, AUTOPLAY_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [autoplay]);

  if (!step) return null;

  return (
    <div className="bg-card rounded-lg border p-6">
      <ol className="flex items-start" aria-label="Crash recovery timeline">
        {CRASH_STEPS.map((item, position) => (
          <li
            key={item.id}
            aria-current={position === index ? 'step' : undefined}
            className="flex flex-1 flex-col items-center gap-2 text-center"
          >
            <button
              type="button"
              onClick={() => {
                setIndex(position);
              }}
              aria-label={`Step ${String(position + 1)}: ${item.label}`}
              className={cn(
                'focus-visible:ring-ring flex h-9 w-9 items-center justify-center rounded-full border text-sm font-semibold transition-colors duration-200 outline-none focus-visible:ring-2 motion-reduce:transition-none',
                position === index
                  ? 'bg-primary text-primary-foreground border-primary'
                  : position < index
                    ? 'bg-secondary text-secondary-foreground'
                    : 'text-muted-foreground',
              )}
            >
              {position + 1}
            </button>
            <span
              className={cn(
                'hidden text-xs sm:block',
                position === index ? 'font-semibold' : 'text-muted-foreground',
              )}
            >
              {item.label}
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-6 min-h-36" aria-live={autoplay ? 'off' : 'polite'}>
        <p className="text-muted-foreground text-xs">
          Step {index + 1} of {CRASH_STEPS.length}
        </p>
        <h3 className="mt-1 text-lg font-semibold">{step.title}</h3>
        <p className="text-muted-foreground mt-2 text-sm">{step.description}</p>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setIndex((current) => Math.max(current - 1, 0));
          }}
          disabled={index === 0}
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Prev
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setIndex((current) => Math.min(current + 1, LAST_INDEX));
          }}
          disabled={index === LAST_INDEX}
        >
          Next
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setAutoplayRequested((current) => !current);
          }}
          disabled={reducedMotion}
          aria-pressed={autoplay}
          title={reducedMotion ? 'Autoplay is off because reduced motion is preferred' : undefined}
        >
          {autoplay ? <Pause className="mr-1 h-4 w-4" /> : <Play className="mr-1 h-4 w-4" />}
          Autoplay
        </Button>
      </div>
    </div>
  );
}
