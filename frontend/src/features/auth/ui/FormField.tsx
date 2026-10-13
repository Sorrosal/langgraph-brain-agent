import { Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';
import type { InputHTMLAttributes } from 'react';
import type { FieldError } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import { VALIDATION_LIMITS } from '../model/auth.schemas';

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
  /** Persistent help text under the input, linked through `aria-describedby`. */
  hint?: string;
  /** Its `message` is a translation key (see `auth.schemas`), resolved here at render time. */
  error?: FieldError | undefined;
}

export function FormField({
  id,
  label,
  hint,
  error,
  type,
  className,
  ...inputProps
}: FormFieldProps) {
  const { t } = useTranslation('auth');
  const [revealed, setRevealed] = useState(false);
  const isPassword = type === 'password';
  const describedBy =
    [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') ||
    undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div className="relative">
        <Input
          id={id}
          type={isPassword && revealed ? 'text' : type}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className={cn('h-11', isPassword && 'pr-12', className)}
          {...inputProps}
        />
        {isPassword && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="absolute top-0 right-0 h-11 w-11"
            aria-label={t(revealed ? 'fields.hidePassword' : 'fields.showPassword')}
            onClick={() => {
              setRevealed((current) => !current);
            }}
          >
            {revealed ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
          </Button>
        )}
      </div>
      {hint && (
        <p id={`${id}-hint`} className="text-muted-foreground text-xs">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-danger-fg text-sm">
          {t(error.message ?? '', VALIDATION_LIMITS)}
        </p>
      )}
    </div>
  );
}
