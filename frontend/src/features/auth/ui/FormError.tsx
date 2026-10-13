import { CircleAlert } from 'lucide-react';

/** Inline server error for a form; `role="alert"` announces it when it appears. */
export function FormError({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="border-danger-border bg-danger-bg text-danger-fg animate-fade-in flex items-start gap-2 rounded-[var(--radius-md)] border px-3 py-2.5 text-sm"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}
