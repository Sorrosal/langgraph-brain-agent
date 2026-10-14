import type { NodeType } from './graph';

export type Tone = 'brand' | 'info' | 'warning' | 'danger' | 'success' | 'neutral';
export type Shape = 'circle' | 'square' | 'diamond' | 'hexagon' | 'triangle';

export interface NodeStyle {
  shape: Shape;
  tone: Tone;
  /** Hollow node (tinted fill, solid outline) for structure; solid node for content. */
  ring: boolean;
}

/** Evolantia tokens per tone. Shape carries the type too, so colour is never the only cue. */
export const TONE_COLORS: Record<Tone, { solid: string; soft: string }> = {
  brand: { solid: 'var(--c-brand)', soft: 'var(--c-brand-bg)' },
  info: { solid: 'var(--c-info)', soft: 'var(--c-info-bg)' },
  warning: { solid: 'var(--c-warning)', soft: 'var(--c-warning-bg)' },
  danger: { solid: 'var(--c-danger)', soft: 'var(--c-danger-bg)' },
  success: { solid: 'var(--c-success)', soft: 'var(--c-success-bg)' },
  neutral: { solid: 'var(--c-fg-muted)', soft: 'var(--c-bg-muted)' },
};

const STYLES: Record<NodeType, NodeStyle> = {
  user: { shape: 'circle', tone: 'brand', ring: false },
  hub: { shape: 'circle', tone: 'neutral', ring: true },
  memory_kind: { shape: 'circle', tone: 'brand', ring: true },
  memory: { shape: 'circle', tone: 'brand', ring: false },
  org: { shape: 'square', tone: 'info', ring: false },
  rule: { shape: 'diamond', tone: 'warning', ring: false },
  guideline: { shape: 'diamond', tone: 'warning', ring: true },
  tool: { shape: 'triangle', tone: 'neutral', ring: false },
  company: { shape: 'square', tone: 'neutral', ring: false },
  contact: { shape: 'circle', tone: 'neutral', ring: false },
  deal: { shape: 'hexagon', tone: 'neutral', ring: false },
  task: { shape: 'hexagon', tone: 'success', ring: false },
  other: { shape: 'circle', tone: 'neutral', ring: true },
};

/** Style of a node; rules turn danger when they block and warning when they ask for approval. */
export function nodeStyle(type: NodeType, group?: string): NodeStyle {
  const style = STYLES[type];
  return type === 'rule' && group === 'block' ? { ...style, tone: 'danger' } : style;
}

/** Space-separated numbers rounded to two decimals, for path data. */
const xy = (...values: number[]) => values.map((v) => Number(v.toFixed(2))).join(' ');

/** SVG path of a shape centred on the origin whose visual weight matches a circle of radius `r`. */
export function shapePath(shape: Shape, r: number): string {
  switch (shape) {
    case 'circle':
      return `M${xy(-r, 0)}a${xy(r, r, 0, 1, 0, 2 * r, 0)}a${xy(r, r, 0, 1, 0, -2 * r, 0)}Z`;
    case 'square': {
      const s = r * 0.88;
      return `M${xy(-s, -s)}H${xy(s)}V${xy(s)}H${xy(-s)}Z`;
    }
    case 'diamond': {
      const d = r * 1.3;
      return `M${xy(0, -d)}L${xy(d, 0)}L${xy(0, d)}L${xy(-d, 0)}Z`;
    }
    case 'hexagon': {
      const h = r * 1.08;
      const points = Array.from({ length: 6 }, (_, i) => {
        const angle = (Math.PI / 3) * i + Math.PI / 6;
        return xy(Math.cos(angle) * h, Math.sin(angle) * h);
      });
      return `M${points.join('L')}Z`;
    }
    case 'triangle': {
      const t = r * 1.3;
      return `M${xy(0, -t)}L${xy(t * 0.866, t * 0.5)}L${xy(-t * 0.866, t * 0.5)}Z`;
    }
  }
}

/** Same stops as `--ev-prism`; SVG cannot reuse the CSS gradient, so the user node repeats them. */
export const PRISM_STOPS = [
  'oklch(0.62 0.2 290)',
  'oklch(0.72 0.14 215)',
  'oklch(0.8 0.13 40)',
] as const;
