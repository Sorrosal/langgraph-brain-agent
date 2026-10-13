import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { RegisterForm } from '@/features/auth';

export default function RegisterPage() {
  const { t } = useTranslation('auth');

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">{t('register.title')}</h1>
        <p className="text-muted-foreground text-sm">{t('register.subtitle')}</p>
      </div>

      <RegisterForm />

      <p className="text-muted-foreground text-center text-sm">
        {t('register.haveAccount')}{' '}
        <Link
          to="/login"
          className="text-brand-ink hover:text-foreground font-medium underline underline-offset-4"
        >
          {t('register.signIn')}
        </Link>
      </p>
    </div>
  );
}
