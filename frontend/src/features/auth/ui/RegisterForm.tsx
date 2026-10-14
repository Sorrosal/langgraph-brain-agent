import { zodResolver } from '@hookform/resolvers/zod';
import { LoaderCircle } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '@/shared/ui/button';
import { cn } from '@/shared/lib/cn';
import { useRegister } from '../api/auth.api';
import { authErrorMessage } from '../model/auth-error';
import { MIN_PASSWORD_LENGTH, registerSchema } from '../model/auth.schemas';
import type { RegisterFormValues } from '../model/auth.schemas';
import { redirectTarget } from '../model/redirect';
import { FormError } from './FormError';
import { FormField } from './FormField';

interface RegisterFormProps {
  className?: string;
}

export function RegisterForm({ className }: RegisterFormProps) {
  const { t } = useTranslation('auth');
  const navigate = useNavigate();
  const location = useLocation();
  const { mutate: registerUser, isPending, error } = useRegister();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  function onSubmit(data: RegisterFormValues) {
    registerUser(data, {
      onSuccess: () => {
        toast.success(t('register.success'));
        void navigate(redirectTarget(location.state), { replace: true });
      },
    });
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(onSubmit)(e)}
      className={cn('flex flex-col gap-4', className)}
      aria-busy={isPending}
      noValidate
    >
      {error && <FormError message={authErrorMessage(error, 'register')} />}
      <FormField
        id="display_name"
        label={t('fields.displayName')}
        autoComplete="name"
        placeholder={t('fields.displayNamePlaceholder')}
        error={errors.display_name}
        {...register('display_name')}
      />
      <FormField
        id="email"
        label={t('fields.email')}
        type="email"
        placeholder={t('fields.emailPlaceholder')}
        autoComplete="email"
        error={errors.email}
        {...register('email')}
      />
      <FormField
        id="password"
        label={t('fields.password')}
        hint={t('fields.passwordHint', { min: MIN_PASSWORD_LENGTH })}
        type="password"
        autoComplete="new-password"
        error={errors.password}
        {...register('password')}
      />
      <FormField
        id="confirmPassword"
        label={t('fields.confirmPassword')}
        type="password"
        autoComplete="new-password"
        error={errors.confirmPassword}
        {...register('confirmPassword')}
      />
      <Button type="submit" size="lg" disabled={isPending} className="mt-1 w-full">
        {isPending && (
          <LoaderCircle className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
        )}
        {isPending ? t('register.submitting') : t('register.submit')}
      </Button>
    </form>
  );
}
