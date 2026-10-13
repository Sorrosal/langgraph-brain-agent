/** Commands stay literal; each step's comment is `landing:quickstart.steps.<id>`. */
export const QUICKSTART_STEPS = [
  { id: 'database', commands: ['docker compose up -d postgres'] },
  {
    id: 'backend',
    commands: ['cd backend', 'uv sync && uv run uvicorn brain_agent.api.app:create_app --factory'],
  },
  { id: 'frontend', commands: ['cd frontend', 'npm ci && npm run dev'] },
] as const;

/** The copyable shell snippet, with each step headed by a numbered comment. */
export function buildQuickstartCode(describe: (id: string) => string): string {
  return QUICKSTART_STEPS.map(
    ({ id, commands }, index) => `# ${String(index + 1)}. ${describe(id)}\n${commands.join('\n')}`,
  ).join('\n\n');
}
