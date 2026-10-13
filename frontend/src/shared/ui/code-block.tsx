import { Check, Copy } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/shared/lib/cn';
import { Button } from './button';

interface CodeBlockProps {
  code: string;
  label: string;
  className?: string;
}

/** Monospace block with a copy-to-clipboard button; `label` names it for assistive tech. */
export function CodeBlock({ code, label, className }: CodeBlockProps) {
  const { t } = useTranslation('landing');
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div
      className={cn('bg-subtle shadow-e1 relative rounded-[var(--radius-lg)] border', className)}
    >
      <Button
        variant="ghost"
        size="sm"
        className="absolute top-2 right-2 max-sm:h-11 max-sm:px-4"
        onClick={() => {
          void handleCopy();
        }}
        aria-label={t('codeBlock.copyLabel', { label })}
      >
        {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
        <span className="text-xs" aria-live="polite">
          {copied ? t('common:actions.copied') : t('common:actions.copy')}
        </span>
      </Button>
      <pre
        className="overflow-x-auto p-4 pt-16 font-mono text-sm leading-relaxed sm:pt-4 sm:pr-28"
        aria-label={label}
        tabIndex={0}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}
