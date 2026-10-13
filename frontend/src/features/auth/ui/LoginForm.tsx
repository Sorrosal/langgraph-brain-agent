import { zodResolver } from '@hookform/resolvers/zod';
import { LoaderCircle } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '@/shared/ui/button';
import { cn } from '@/shared/lib/cn';
import { useLogin } from '../api/auth.api';
import { authErrorMessage } from '../model/auth-error';
import { loginSchema } from '../model/auth.schemas';
import type { LoginFormValues } from '../model/auth.schemas';
import { FormError } from './FormError';
import { FormField } from './FormField';

interface LoginFormProps {
  className?: string;
}

export function LoginForm({ className }: LoginFormProps) {
  const { t } = useTranslation('auth');
  const navigate = useNavigate();
  const { mutate: login, isPending, error } = useLogin();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  function onSubmit(data: LoginFormValues) {
    login(data, {
      onSuccess: () => {
        toast.success(t('login.success'));
        void navigate('/app/chat');
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
      {error && <FormError message={authErrorMessage(error, 'login')} />}
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
        type="password"
        autoComplete="current-password"
        error={errors.password}
        {...register('password')}
      />
      <Button type="submit" size="lg" disabled={isPending} className="mt-1 w-full">
        {isPending && (
          <LoaderCircle className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
        )}
        {isPending ? t('login.submitting') : t('login.submit')}
      </Button>
    </form>
  );
}
