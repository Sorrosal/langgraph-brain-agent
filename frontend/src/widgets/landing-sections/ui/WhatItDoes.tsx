import { Ban, ShieldCheck } from 'lucide-react';
import { Section } from '@/shared/ui/section';
import { BLOCKED, NEEDS_APPROVAL, USE_CASES } from '../model/what-it-does';

export function WhatItDoes() {
  return (
    <Section
      id="what-it-does"
      title="What it does"
      description="An operations assistant for a small team. It acts on email, CRM and tasks, and the rules decide what it may do alone."
    >
      <ul className="grid gap-4 sm:grid-cols-3">
        {USE_CASES.map(({ title, text }) => (
          <li key={title} className="bg-card rounded-lg border p-5">
            <h3 className="font-semibold">{title}</h3>
            <p className="text-muted-foreground mt-2 text-sm">{text}</p>
          </li>
        ))}
      </ul>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="bg-card rounded-lg border p-5">
          <h3 className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Needs approval
          </h3>
          <ul className="text-muted-foreground mt-3 list-disc space-y-1 pl-5 text-sm">
            {NEEDS_APPROVAL.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="bg-card rounded-lg border p-5">
          <h3 className="flex items-center gap-2 font-semibold">
            <Ban className="h-4 w-4" aria-hidden="true" />
            Blocked
          </h3>
          <ul className="text-muted-foreground mt-3 list-disc space-y-1 pl-5 text-sm">
            {BLOCKED.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </Section>
  );
}
