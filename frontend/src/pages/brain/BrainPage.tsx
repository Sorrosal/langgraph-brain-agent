import { useState } from 'react';
import { BrainMemories } from '@/widgets/brain-memories';
import { BrainRules } from '@/widgets/brain-rules';
import { Tabs } from '@/shared/ui/tabs';

const TABS = [
  { id: 'memories', label: 'Memories' },
  { id: 'rules', label: 'Rules' },
] as const;

export default function BrainPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('memories');

  return (
    <div className="flex max-w-4xl flex-col gap-4 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Brain</h1>
        <p className="text-muted-foreground">What the agent remembers and the rules it follows.</p>
      </div>
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      {tab === 'memories' ? <BrainMemories /> : <BrainRules />}
    </div>
  );
}
