import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '@/shared/ui/button';
import { cn } from '@/shared/lib/cn';
import { useRegister } from '../api/auth.api';
import { registerSchema } from '../model/auth.schemas';
import type { RegisterFormValues } from '../model/auth.schemas';
import { FormField } from './FormField';

interface RegisterFormProps {
  className?: string;
}

export function RegisterForm({ className }: RegisterFormProps) {
  const navigate = useNavigate();
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
        toast.success('Account created! Welcome aboard.');
        void navigate('/app/chat');
      },
    });
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(onSubmit)(e)}
      className={cn('flex flex-col gap-4', className)}
      noValidate
    >
      {error && (
        <p role="alert" className="text-destructive text-sm">
          {error.message}
        </p>
      )}
      <FormField
        id="display_name"
        label="Display name"
        autoComplete="name"
        placeholder="Jane Smith"
        error={errors.display_name}
        {...register('display_name')}
      />
      <FormField
        id="email"
        label="Email"
        type="email"
        placeholder="you@example.com"
        autoComplete="email"
        error={errors.email}
        {...register('email')}
      />
      <FormField
        id="password"
        label="Password (min. 10 characters)"
        type="password"
        autoComplete="new-password"
        error={errors.password}
        {...register('password')}
      />
      <FormField
        id="confirmPassword"
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        error={errors.confirmPassword}
        {...register('confirmPassword')}
      />
      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? 'Creating account…' : 'Create account'}
      </Button>
    </form>
  );
}
