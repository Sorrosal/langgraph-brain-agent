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
      className={cn('mx-auto max-w-5xl scroll-mt-16 px-4 py-14', className)}
    >
      <h2 id={`${id}-title`} className="text-3xl font-bold tracking-tight">
        {title}
      </h2>
      {description && <p className="text-muted-foreground mt-3 max-w-3xl">{description}</p>}
      <div className="mt-8">{children}</div>
    </section>
  );
}
