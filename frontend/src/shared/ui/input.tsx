import * as React from 'react';
import { cn } from '@/shared/lib/cn';

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'border-input bg-elevated file:text-foreground placeholder:text-faint focus-visible:border-brand focus-visible:ring-brand/25 aria-[invalid=true]:border-danger aria-[invalid=true]:ring-danger/20 flex h-10 w-full rounded-[var(--radius-md)] border px-3 py-1 text-base transition-[border-color,box-shadow] file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:ring-4 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm',
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = 'Input';

export { Input };
