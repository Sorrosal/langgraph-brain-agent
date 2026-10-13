/** Positions only: titles and details come from `landing:architecture.boxes.<id>`. */
export interface ArchitectureBox {
  id: 'react' | 'api' | 'runtime' | 'openai' | 'postgres';
  x: number;
  y: number;
}

export const ARCH_VIEW_BOX = '0 0 800 300';
export const ARCH_BOX_WIDTH = 220;
export const ARCH_BOX_HEIGHT = 84;
/** Characters per line of a box detail, so longer (translated) text wraps inside the box. */
export const ARCH_DETAIL_MAX_CHARS = 32;

export const ARCH_BOXES: readonly ArchitectureBox[] = [
  { id: 'react', x: 120, y: 60 },
  { id: 'api', x: 400, y: 60 },
  { id: 'runtime', x: 680, y: 60 },
  { id: 'openai', x: 680, y: 240 },
  { id: 'postgres', x: 400, y: 240 },
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
