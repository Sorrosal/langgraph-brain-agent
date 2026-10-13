import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BrainMemories } from '@/widgets/brain-memories';
import { BrainRules } from '@/widgets/brain-rules';
import { Tabs } from '@/shared/ui/tabs';

type TabId = 'memories' | 'rules';

export default function BrainPage() {
  const { t } = useTranslation('brain');
  const [tab, setTab] = useState<TabId>('memories');
  const tabs = [
    { id: 'memories', label: t('tabs.memories') },
    { id: 'rules', label: t('tabs.rules') },
  ] as const;

  return (
    <div className="animate-fade-in mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t('page.title')}</h1>
        <p className="text-muted-foreground text-sm">{t('page.description')}</p>
      </header>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === 'memories' ? <BrainMemories /> : <BrainRules />}
    </div>
  );
}
