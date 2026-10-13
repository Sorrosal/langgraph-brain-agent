import { BrainCircuit, ListChecks, Mail, UserPlus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { AssistantMark } from '@/entities/message';
import { cn } from '@/shared/lib/cn';

const SUGGESTIONS = [
  { key: 'tasks', icon: ListChecks },
  { key: 'contact', icon: UserPlus },
  { key: 'email', icon: Mail },
  { key: 'memory', icon: BrainCircuit },
] as const;

interface ChatSuggestionsProps {
  title: string;
  subtitle?: string;
  onPick: (prompt: string) => void;
  disabled?: boolean;
  className?: string;
}

/** Welcome block: the assistant mark, a title and prompts that start a conversation. */
export function ChatSuggestions({
  title,
  subtitle,
  onPick,
  disabled = false,
  className,
}: ChatSuggestionsProps) {
  const { t } = useTranslation('chat');
  return (
    <div className={cn('animate-slide-up flex flex-col items-center gap-6 text-center', className)}>
      <AssistantMark className="size-12" />
      <div className="flex max-w-lg flex-col gap-2">
        <h2 className="text-2xl font-semibold">{title}</h2>
        {subtitle && <p className="text-muted-foreground text-sm">{subtitle}</p>}
      </div>
      <div className="flex w-full max-w-2xl flex-col gap-2">
        <p className="text-faint text-2xs font-medium tracking-wide uppercase">
          {t('welcome.suggestionsLabel')}
        </p>
        <ul className="grid gap-2 sm:grid-cols-2">
          {SUGGESTIONS.map(({ key, icon: Icon }) => {
            const prompt = t(`suggestions.${key}`);
            return (
              <li key={key}>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    onPick(prompt);
                  }}
                  className="bg-elevated shadow-e1 hover:border-brand/40 hover:bg-subtle flex h-full min-h-14 w-full items-start gap-3 rounded-[var(--radius-lg)] border px-4 py-3 text-left text-sm transition-colors disabled:pointer-events-none disabled:opacity-50"
                >
                  <Icon className="text-brand-ink mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <span>{prompt}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
