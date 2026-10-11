export const USE_CASES = [
  {
    title: 'Email',
    text: 'Reads and drafts messages and sends them on behalf of the team.',
  },
  {
    title: 'CRM',
    text: 'Looks up contacts and deals and updates records.',
  },
  {
    title: 'Tasks',
    text: 'Creates, updates and completes tasks, and deletes them when approved.',
  },
] as const;

/** Mirrors `rules/default.yaml`. */
export const NEEDS_APPROVAL = [
  'Emails to recipients outside @acme.com, including cc',
  'Bulk emails to more than 5 recipients',
  'Deal updates above 10000',
  'Deleting a task',
] as const;

export const BLOCKED = ['Deleting CRM records'] as const;
