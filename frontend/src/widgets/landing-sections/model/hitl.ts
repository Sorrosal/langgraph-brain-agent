export const HITL_LIFECYCLE = [
  { label: 'Pause', text: 'A sensitive tool call stops the graph at an interrupt().' },
  {
    label: 'Decision',
    text: 'A human approves, edits the arguments, rejects, or responds with free text.',
  },
  { label: 'Resume', text: 'The graph continues from the checkpoint with that decision applied.' },
] as const;

export const HITL_DECISIONS = ['approve', 'edit', 'reject', 'respond'] as const;

export const UNCERTAIN_OPTIONS = [
  { label: 'Confirm done', text: 'The side effect did happen; keep its result.' },
  { label: 'Retry', text: 'Run the tool again, explicitly authorized by a human.' },
  { label: 'Skip', text: 'Do not run it; the agent is told it was skipped.' },
] as const;

export const HITL_NOTES = [
  'Pending approvals live in the PostgreSQL checkpoint, so they survive restarts and deploys.',
  'An execution whose outcome is unknown (the process died mid-tool) is never guessed: it waits for a human.',
] as const;
