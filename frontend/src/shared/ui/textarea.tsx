import * as React from 'react';
import { cn } from '@/shared/lib/cn';

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          'border-input bg-elevated placeholder:text-faint focus-visible:border-brand focus-visible:ring-brand/25 aria-[invalid=true]:border-danger flex min-h-[60px] w-full rounded-[var(--radius-md)] border px-3 py-2 text-base transition-[border-color,box-shadow] focus-visible:ring-4 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm',
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Textarea.displayName = 'Textarea';

export { Textarea };
