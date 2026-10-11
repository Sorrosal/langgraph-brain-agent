import type { InputHTMLAttributes } from 'react';
import type { FieldError } from 'react-hook-form';
import { Input } from '@/shared/ui/input';

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
  error?: FieldError | undefined;
}

export function FormField({ id, label, error, ...inputProps }: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <Input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        {...inputProps}
      />
      {error && (
        <p id={`${id}-error`} className="text-destructive text-sm">
          {error.message}
        </p>
      )}
    </div>
  );
}
