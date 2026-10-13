import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { LoginForm } from '@/features/auth';

export default function LoginPage() {
  const { t } = useTranslation('auth');

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">{t('login.title')}</h1>
        <p className="text-muted-foreground text-sm">{t('login.subtitle')}</p>
      </div>

      <LoginForm />

      <p className="text-muted-foreground text-center text-sm">
        {t('login.noAccount')}{' '}
        <Link
          to="/register"
          className="text-brand-ink hover:text-foreground font-medium underline underline-offset-4"
        >
          {t('login.signUp')}
        </Link>
      </p>
    </div>
  );
}
