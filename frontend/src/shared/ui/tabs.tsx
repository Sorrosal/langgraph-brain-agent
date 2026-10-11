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
    <div role="tablist" className={cn('flex gap-1 border-b', className)}>
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
            '-mb-px border-b-2 px-4 py-2 text-sm transition-colors',
            tab.id === value
              ? 'border-primary font-medium'
              : 'text-muted-foreground hover:text-foreground border-transparent',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
