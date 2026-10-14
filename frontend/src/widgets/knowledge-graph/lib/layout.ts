import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from 'd3-force';
import type { SimulationLinkDatum, SimulationNodeDatum } from 'd3-force';
import type { GraphEdge, GraphNode } from '../api/knowledge-graph.api';

export interface Point {
  x: number;
  y: number;
}
export type Positions = Map<string, Point>;

interface SimNode extends SimulationNodeDatum {
  id: string;
  r: number;
}
type SimLink = SimulationLinkDatum<SimNode> & { kind: string };

/** Fixed budget: the layout is settled off-screen, so what renders is stable and never jitters. */
const TICKS = 300;

/**
 * Force-directed layout, computed once. d3-force is deterministic (phyllotaxis start, seeded
 * jitter), so the same graph always lands in the same place. Edges must reference existing
 * nodes; run `sanitizeGraph` first.
 */
export function computeLayout(
  nodes: readonly GraphNode[],
  edges: readonly GraphEdge[],
  radii: ReadonlyMap<string, number>,
  ticks = TICKS,
): Positions {
  const simNodes: SimNode[] = nodes.map((n) => ({ id: n.id, r: radii.get(n.id) ?? 6 }));
  const links: SimLink[] = edges.map((e) => ({ source: e.source, target: e.target, kind: e.kind }));

  const simulation = forceSimulation(simNodes)
    .force(
      'link',
      forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        // `mentions` is a loose cross-reference: long and weak, so it never drags clusters together.
        .distance((l) =>
          l.kind === 'mentions' ? 150 : 64 + radiusOf(l.source) + radiusOf(l.target),
        )
        .strength((l) => (l.kind === 'mentions' ? 0.03 : 0.6)),
    )
    .force(
      'charge',
      forceManyBody<SimNode>()
        .strength((d) => -110 - d.r * 10)
        .distanceMax(420),
    )
    .force(
      'collide',
      forceCollide<SimNode>((d) => d.r + 10),
    )
    .force('center', forceCenter(0, 0))
    // Weak pull to the middle keeps disconnected pieces (a deal with no contact) close by.
    .force('x', forceX<SimNode>(0).strength(0.035))
    .force('y', forceY<SimNode>(0).strength(0.035))
    .stop();
  simulation.tick(ticks);

  return new Map(simNodes.map((n) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }]));
}

function radiusOf(end: string | number | SimNode): number {
  return typeof end === 'object' ? end.r : 6;
}

export interface View {
  /** Pan, in screen pixels. */
  x: number;
  y: number;
  /** Zoom factor. */
  k: number;
}

export const MIN_ZOOM = 0.15;
export const MAX_ZOOM = 4;
const clampZoom = (k: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, k));

/** View that centres `points` (each with a radius) in a `w` by `h` canvas with some padding. */
export function fitView(
  points: readonly (Point & { r: number })[],
  size: { w: number; h: number },
  padding = 48,
): View {
  if (points.length === 0) return { x: size.w / 2, y: size.h / 2, k: 1 };
  const minX = Math.min(...points.map((p) => p.x - p.r));
  const maxX = Math.max(...points.map((p) => p.x + p.r));
  const minY = Math.min(...points.map((p) => p.y - p.r));
  const maxY = Math.max(...points.map((p) => p.y + p.r));
  const k = clampZoom(
    Math.min(
      (size.w - 2 * padding) / Math.max(maxX - minX, 1),
      (size.h - 2 * padding) / Math.max(maxY - minY, 1),
      1.5,
    ),
  );
  return { k, x: size.w / 2 - ((minX + maxX) / 2) * k, y: size.h / 2 - ((minY + maxY) / 2) * k };
}

/** Zoom by `factor` keeping the screen point (`px`, `py`) fixed under the cursor. */
export function zoomAt(view: View, factor: number, px: number, py: number): View {
  const k = clampZoom(view.k * factor);
  const ratio = k / view.k;
  return { k, x: px - (px - view.x) * ratio, y: py - (py - view.y) * ratio };
}
