import { useState } from 'react';
import { ContactsTab, DealsTab, EmailsTab, TasksTab } from '@/widgets/data-tables';
import { Tabs } from '@/shared/ui/tabs';

const TABS = [
  { id: 'contacts', label: 'Contacts' },
  { id: 'deals', label: 'Deals' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'emails', label: 'Emails' },
] as const;

const PANELS = {
  contacts: ContactsTab,
  deals: DealsTab,
  tasks: TasksTab,
  emails: EmailsTab,
};

export default function DataPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('contacts');
  const Panel = PANELS[tab];

  return (
    <div className="flex flex-col gap-4 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Data</h1>
        <p className="text-muted-foreground">Business data the agent works with (read-only).</p>
      </div>
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      <Panel />
    </div>
  );
}
