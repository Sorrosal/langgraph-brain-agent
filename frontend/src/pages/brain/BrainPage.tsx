import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BrainMemories } from '@/widgets/brain-memories';
import { BrainRules } from '@/widgets/brain-rules';
import { KnowledgeGraph } from '@/widgets/knowledge-graph';
import { OrgKnowledge } from '@/widgets/org-knowledge';
import { cn } from '@/shared/lib/cn';
import { Tabs } from '@/shared/ui/tabs';

type TabId = 'memories' | 'org' | 'rules' | 'graph';

export default function BrainPage() {
  const { t } = useTranslation('brain');
  const [tab, setTab] = useState<TabId>('memories');
  const tabs = [
    { id: 'memories', label: t('tabs.memories') },
    { id: 'org', label: t('tabs.org') },
    { id: 'rules', label: t('tabs.rules') },
    { id: 'graph', label: t('tabs.graph') },
  ] as const;

  return (
    <div
      className={cn(
        'animate-fade-in mx-auto flex w-full flex-col gap-6 p-4 sm:p-6',
        // The graph needs room; the lists read better in a narrow column.
        tab === 'graph' ? 'max-w-6xl' : 'max-w-4xl',
      )}
    >
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t('page.title')}</h1>
        <p className="text-muted-foreground text-sm">{t('page.description')}</p>
      </header>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === 'memories' && <BrainMemories />}
      {tab === 'org' && <OrgKnowledge />}
      {tab === 'rules' && <BrainRules />}
      {tab === 'graph' && <KnowledgeGraph />}
    </div>
  );
}
