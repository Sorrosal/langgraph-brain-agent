import { Section } from '@/shared/ui/section';
import { BRAIN_CARDS } from '../model/brain';

export function Brain() {
  return (
    <Section
      id="brain"
      title="The brain"
      description="Memory, rules and context assembly sit around the loop, so the agent knows what it knows and what it may do."
    >
      <div className="grid gap-4 md:grid-cols-3">
        {BRAIN_CARDS.map(({ title, items }) => (
          <div key={title} className="bg-card rounded-lg border p-5">
            <h3 className="font-semibold">{title}</h3>
            <ul className="text-muted-foreground mt-3 list-disc space-y-1 pl-5 text-sm">
              {items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Section>
  );
}
