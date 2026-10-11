import { Check, Copy } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/shared/lib/cn';
import { Button } from './button';

interface CodeBlockProps {
  code: string;
  label: string;
  className?: string;
}

/** Monospace block with a copy-to-clipboard button; `label` names it for assistive tech. */
export function CodeBlock({ code, label, className }: CodeBlockProps) {
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
    <div className={cn('bg-secondary relative rounded-lg border', className)}>
      <Button
        variant="ghost"
        size="sm"
        className="absolute top-2 right-2"
        onClick={() => {
          void handleCopy();
        }}
        aria-label={`Copy ${label}`}
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        <span className="ml-1.5 text-xs" aria-live="polite">
          {copied ? 'Copied' : 'Copy'}
        </span>
      </Button>
      <pre
        className="overflow-x-auto p-4 pt-12 text-sm leading-relaxed sm:pt-4 sm:pr-24"
        aria-label={label}
        tabIndex={0}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}
