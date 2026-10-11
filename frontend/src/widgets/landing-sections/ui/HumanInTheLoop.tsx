import { Badge } from '@/shared/ui/badge';
import { Section } from '@/shared/ui/section';
import { HITL_DECISIONS, HITL_LIFECYCLE, HITL_NOTES, UNCERTAIN_OPTIONS } from '../model/hitl';

export function HumanInTheLoop() {
  return (
    <Section
      id="human-in-the-loop"
      title="Human in the loop"
      description="Sensitive actions wait for a person. The wait is part of the durable state, not a process held in memory."
    >
      <ol className="grid gap-4 md:grid-cols-3">
        {HITL_LIFECYCLE.map(({ label, text }, index) => (
          <li key={label} className="bg-card rounded-lg border p-5">
            <p className="text-muted-foreground text-xs">Step {index + 1}</p>
            <h3 className="font-semibold">{label}</h3>
            <p className="text-muted-foreground mt-2 text-sm">{text}</p>
            {label === 'Decision' && (
              <ul className="mt-3 flex flex-wrap gap-2" aria-label="Decisions">
                {HITL_DECISIONS.map((decision) => (
                  <li key={decision}>
                    <Badge variant="outline">{decision}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
      <ul className="text-muted-foreground mt-6 list-disc space-y-1 pl-5 text-sm">
        {HITL_NOTES.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
      <h3 className="mt-8 font-semibold">Uncertain executions</h3>
      <ul className="mt-3 grid gap-4 md:grid-cols-3">
        {UNCERTAIN_OPTIONS.map(({ label, text }) => (
          <li key={label} className="bg-card rounded-lg border p-4">
            <p className="font-medium">{label}</p>
            <p className="text-muted-foreground mt-1 text-sm">{text}</p>
          </li>
        ))}
      </ul>
    </Section>
  );
}
