import { Lock } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContacts } from '@/entities/contact';
import { useDeals } from '@/entities/deal';
import { useTasks } from '@/entities/task';
import { ContactsTab, DealsTab, EmailsTab, TasksTab } from '@/widgets/data-tables';
import { Tabs } from '@/shared/ui/tabs';

const TAB_IDS = ['contacts', 'deals', 'tasks', 'emails'] as const;
type TabId = (typeof TAB_IDS)[number];

const PANELS = {
  contacts: ContactsTab,
  deals: DealsTab,
  tasks: TasksTab,
  emails: EmailsTab,
} satisfies Record<TabId, React.ComponentType>;

/** The entity hooks fetch at most this many rows, so a full list may hide more. */
const FETCH_LIMIT = 100;

export default function DataPage() {
  const { t } = useTranslation('data');
  const [tab, setTab] = useState<TabId>('contacts');
  const Panel = PANELS[tab];

  // Same query keys as the unfiltered panels, so each shares one request with its panel.
  // Emails are not counted: the list depends on the folder.
  const contacts = useContacts('').data;
  const deals = useDeals('').data;
  const tasks = useTasks('').data;
  const counts: Partial<Record<TabId, number>> = {
    ...(contacts && { contacts: contacts.length }),
    ...(deals && { deals: deals.length }),
    ...(tasks && { tasks: tasks.length }),
  };

  const tabs = TAB_IDS.map((id) => {
    const label = t(`tabs.${id}`);
    const count = counts[id];
    return {
      id,
      label:
        count === undefined
          ? label
          : t('tabs.withCount', {
              label,
              total: count >= FETCH_LIMIT ? `${String(FETCH_LIMIT)}+` : count,
            }),
    };
  });

  return (
    <div className="animate-fade-in mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 sm:p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t('page.title')}</h1>
        <p className="text-muted-foreground text-sm">{t('page.description')}</p>
        <p className="text-faint mt-1 flex items-center gap-1.5 text-xs">
          <Lock className="size-3 shrink-0" aria-hidden />
          {t('page.readOnlyHint')}
        </p>
      </header>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      <Panel />
    </div>
  );
}
