import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/shared/lib/cn';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-2xs font-semibold whitespace-nowrap',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-brand-bg text-brand-ink',
        secondary: 'border-transparent bg-secondary text-muted-foreground',
        destructive: 'border-danger-border bg-danger-bg text-danger-fg',
        success: 'border-success-border bg-success-bg text-success-fg',
        warning: 'border-warning-border bg-warning-bg text-warning-fg',
        info: 'border-info-border bg-info-bg text-info-fg',
        outline: 'text-foreground border-input',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
