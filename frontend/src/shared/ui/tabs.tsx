import { cn } from '@/shared/lib/cn';

interface TabsProps<T extends string> {
  tabs: readonly { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
  className?: string;
}

/** Minimal controlled tab strip; the caller renders the active panel. */
export function Tabs<T extends string>({ tabs, value, onChange, className }: TabsProps<T>) {
  return (
    <div
      role="tablist"
      className={cn(
        'bg-muted inline-flex w-fit max-w-full gap-1 overflow-x-auto rounded-[var(--radius-md)] p-1',
        className,
      )}
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === value}
          onClick={() => {
            onChange(tab.id);
          }}
          className={cn(
            'rounded-[var(--radius-sm)] px-3.5 py-1.5 text-sm font-medium whitespace-nowrap transition-colors',
            tab.id === value
              ? 'bg-elevated text-foreground shadow-e1'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
