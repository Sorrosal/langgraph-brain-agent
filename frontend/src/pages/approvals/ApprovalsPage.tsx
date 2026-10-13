import { useTranslation } from 'react-i18next';
import { ApprovalQueue } from '@/widgets/approval-queue';

export default function ApprovalsPage() {
  const { t } = useTranslation('approvals');

  return (
    <div className="animate-fade-in mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t('page.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('page.description')}</p>
      </header>
      <ApprovalQueue />
    </div>
  );
}
