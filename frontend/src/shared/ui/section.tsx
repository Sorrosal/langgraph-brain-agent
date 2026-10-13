import { cn } from '@/shared/lib/cn';

interface SectionProps {
  id: string;
  title: string;
  description?: string;
  className?: string;
  children: React.ReactNode;
}

/** Page section with an `h2` heading wired to the landmark through `aria-labelledby`. */
export function Section({ id, title, description, className, children }: SectionProps) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className={cn('mx-auto max-w-5xl scroll-mt-16 px-4 py-12 sm:px-6 sm:py-16', className)}
    >
      <h2
        id={`${id}-title`}
        className="font-display text-2xl font-semibold tracking-tight text-balance sm:text-3xl"
      >
        {title}
      </h2>
      {description && (
        <p className="text-muted-foreground text-reading mt-3 max-w-3xl text-pretty">
          {description}
        </p>
      )}
      <div className="mt-8">{children}</div>
    </section>
  );
}
