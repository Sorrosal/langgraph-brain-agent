export interface CrashStep {
  id: string;
  label: string;
  title: string;
  description: string;
}

export const AUTOPLAY_INTERVAL_MS = 4000;

export const CRASH_STEPS: readonly CrashStep[] = [
  {
    id: 'checkpoint',
    label: 'Checkpoint',
    title: 'A checkpoint is saved after every step',
    description:
      'The graph state is written to PostgreSQL before the next step starts (synchronous durability). The run is also registered with a lease that its owner keeps renewing with a heartbeat.',
  },
  {
    id: 'crash',
    label: 'Crash',
    title: 'The worker crashes mid-tool',
    description:
      'The process dies while the send_email tool is running. Nothing renews the lease anymore, so it expires. The last checkpoint is intact.',
  },
  {
    id: 'claim',
    label: 'Recover',
    title: 'A recovery worker claims the orphaned run',
    description:
      'The recovery worker looks for runs whose lease expired and claims them with FOR UPDATE SKIP LOCKED, so two workers never take the same run. Each claim bumps a fencing token, which makes a stale owner unable to renew or finish the run.',
  },
  {
    id: 'ledger',
    label: 'Ledger',
    title: 'The tool ledger decides what is safe to repeat',
    description:
      'Every tool call is recorded under thread id and tool call id. A succeeded call replays its stored result instead of running again. A call left started whose tool is not retry-safe has an unknown outcome, so a human decides: confirm done, retry or skip.',
  },
  {
    id: 'resume',
    label: 'Resume',
    title: 'The run resumes and the email is sent exactly once',
    description:
      'The graph continues from the last checkpoint with the ledger as the source of truth. The email is never duplicated: it is either replayed from the ledger or confirmed by a human first.',
  },
];
