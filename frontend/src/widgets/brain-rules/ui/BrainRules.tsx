import { RuleCard, useRules } from '@/entities/rule';
import { RuleFileEditor } from '@/features/edit-rules';
import { selectIsAdmin, useAuthStore } from '@/features/auth';
import { Badge } from '@/shared/ui/badge';
import { Skeleton } from '@/shared/ui/skeleton';

export function BrainRules() {
  const isAdmin = useAuthStore(selectIsAdmin);
  const { data: rules, isLoading, isError } = useRules();

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError || !rules) return <p className="text-destructive text-sm">Could not load rules.</p>;

  const guidelines = [...rules.guidelines].sort((a, b) => b.priority - a.priority);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Version</span>
        <code className="font-mono">{rules.version_hash}</code>
        {!isAdmin && <Badge variant="outline">read-only</Badge>}
      </div>

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold">Persona</h2>
        <p className="text-sm whitespace-pre-wrap">
          {rules.persona ?? <span className="text-muted-foreground">No persona set.</span>}
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold">Guidelines</h2>
        <ul className="flex flex-col gap-2">
          {guidelines.map((guideline) => (
            <li key={guideline.id} className="flex items-start gap-2 text-sm">
              <Badge variant="secondary">P{guideline.priority}</Badge>
              <span>{guideline.text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold">Hard rules</h2>
        <ul className="grid gap-2 md:grid-cols-2">
          {rules.hard_rules.map((rule) => (
            <li key={rule.id}>
              <RuleCard rule={rule} />
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="font-semibold">Rule files</h2>
        {rules.files.map((file) => (
          // remount when the server content changes (after a save) to reset the draft
          <RuleFileEditor
            key={`${file.name}:${rules.version_hash}`}
            name={file.name}
            content={file.content}
            readOnly={!isAdmin}
          />
        ))}
      </section>
    </div>
  );
}
