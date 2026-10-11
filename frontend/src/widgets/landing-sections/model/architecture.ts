export interface ArchitectureBox {
  id: string;
  title: string;
  detail: string;
  x: number;
  y: number;
}

export const ARCH_VIEW_BOX = '0 0 800 300';
export const ARCH_BOX_WIDTH = 180;
export const ARCH_BOX_HEIGHT = 70;

export const ARCH_BOXES: readonly ArchitectureBox[] = [
  { id: 'react', title: 'React', detail: 'Feature-Sliced Design UI', x: 100, y: 60 },
  { id: 'api', title: 'FastAPI', detail: 'SSE streaming, JWT auth', x: 400, y: 60 },
  {
    id: 'runtime',
    title: 'LangGraph runtime',
    detail: 'Graph, runner, recovery worker',
    x: 700,
    y: 60,
  },
  { id: 'openai', title: 'OpenAI', detail: 'Chat and embedding models', x: 700, y: 240 },
  {
    id: 'postgres',
    title: 'PostgreSQL',
    detail: 'Checkpoints, store + pgvector, runs, tool ledger',
    x: 400,
    y: 240,
  },
];

/** Pairs of box ids joined by a line, drawn in order. */
export const ARCH_LINKS: readonly (readonly [string, string])[] = [
  ['react', 'api'],
  ['api', 'runtime'],
  ['runtime', 'openai'],
  ['runtime', 'postgres'],
  ['api', 'postgres'],
];

export const STACK_BADGES = [
  'React 19',
  'TypeScript',
  'Tailwind CSS',
  'Vite',
  'FastAPI',
  'LangGraph',
  'PostgreSQL',
  'pgvector',
  'OpenAI',
  'Docker Compose',
] as const;
