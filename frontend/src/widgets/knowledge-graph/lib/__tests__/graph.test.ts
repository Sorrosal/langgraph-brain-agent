import { describe, expect, it } from 'vitest';
import type { GraphEdge, GraphNode } from '../../api/knowledge-graph.api';
import {
  computeDegrees,
  countByType,
  filterGraph,
  groupByType,
  isGraphEmpty,
  matchNodes,
  neighboursOf,
  nodeRadius,
  nodeType,
  sanitizeGraph,
} from '../graph';
import type { NodeType } from '../graph';
import { computeLayout, fitView, MAX_ZOOM, zoomAt } from '../layout';
import { nodeStyle, shapePath } from '../node-style';

const node = (id: string, type: string, extra: Partial<GraphNode> = {}): GraphNode => ({
  id,
  type,
  label: id,
  ...extra,
});
const edge = (source: string, target: string, kind = 'has'): GraphEdge => ({
  source,
  target,
  kind,
});

const nodes = [
  node('user', 'user'),
  node('kind:fact', 'memory_kind'),
  node('mem:1', 'memory', { label: 'Works at Globex', detail: 'Ada Lovelace works at Globex' }),
  node('mem:2', 'memory', { label: 'Likes tea' }),
  node('contact:1', 'contact', { label: 'Ada Lovelace', detail: 'ada@globex.com' }),
  node('company:globex', 'company', { label: 'Globex' }),
  node('hologram', 'something_new'),
];
const edges = [
  edge('user', 'kind:fact'),
  edge('kind:fact', 'mem:1'),
  edge('kind:fact', 'mem:2'),
  edge('mem:1', 'contact:1', 'mentions'),
  edge('mem:1', 'company:globex', 'mentions'),
  edge('contact:1', 'company:globex', 'works_at'),
];

describe('graph helpers', () => {
  it('maps unknown node types to the generic `other` type', () => {
    expect(nodeType(node('a', 'memory'))).toBe('memory');
    expect(nodeType(node('a', 'something_new'))).toBe('other');
  });

  it('drops duplicate nodes, duplicate edges, self-loops and edges to missing nodes', () => {
    const clean = sanitizeGraph({
      nodes: [node('a', 'memory'), node('a', 'memory'), node('b', 'contact')],
      edges: [edge('a', 'b'), edge('a', 'b'), edge('a', 'a'), edge('a', 'ghost')],
    });
    expect(clean.nodes.map((n) => n.id)).toEqual(['a', 'b']);
    expect(clean.edges).toEqual([edge('a', 'b')]);
  });

  it('computes the degree of every node, including isolated ones', () => {
    const degrees = computeDegrees(nodes, edges);
    expect(degrees.get('mem:1')).toBe(3);
    expect(degrees.get('kind:fact')).toBe(3);
    expect(degrees.get('hologram')).toBe(0);
  });

  it('grows the radius with the degree up to a cap', () => {
    expect(nodeRadius('memory', 9)).toBeGreaterThan(nodeRadius('memory', 1));
    expect(nodeRadius('memory', 1_000_000)).toBe(nodeRadius('memory', 10_000));
  });

  it('counts nodes by type and detects an empty graph', () => {
    const counts = countByType(nodes);
    expect(counts.get('memory')).toBe(2);
    expect(counts.get('other')).toBe(1);
    expect(isGraphEmpty([node('user', 'user')])).toBe(true);
    expect(isGraphEmpty([node('user', 'user'), node('kind:fact', 'memory_kind')])).toBe(true);
    expect(isGraphEmpty([node('user', 'user'), node('mem:1', 'memory')])).toBe(false);
  });

  it('filters by type and drops the edges of hidden nodes', () => {
    const hidden = new Set<NodeType>(['memory']);
    const result = filterGraph({ nodes, edges }, hidden);
    expect(result.nodes.some((n) => n.type === 'memory')).toBe(false);
    expect(result.edges).toEqual([
      edge('user', 'kind:fact'),
      edge('contact:1', 'company:globex', 'works_at'),
    ]);
  });

  it('returns the same graph when nothing is hidden', () => {
    const graph = { nodes, edges };
    expect(filterGraph(graph, new Set())).toBe(graph);
  });

  it('matches the search on label and detail, ignoring case, and is null when blank', () => {
    expect(matchNodes(nodes, '   ')).toBeNull();
    expect([...(matchNodes(nodes, 'GLOBEX') ?? [])].sort()).toEqual([
      'company:globex',
      'contact:1',
      'mem:1',
    ]);
    expect(matchNodes(nodes, 'zzz')?.size).toBe(0);
  });

  it('lists each neighbour once, whatever the edge direction', () => {
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const result = neighboursOf('mem:1', [...edges, edge('contact:1', 'mem:1', 'mentions')], byId);
    expect(result.map((r) => r.node.id)).toEqual(['kind:fact', 'contact:1', 'company:globex']);
  });

  it('groups nodes by type in legend order', () => {
    expect(groupByType(nodes).map(([type]) => type)).toEqual([
      'user',
      'memory_kind',
      'memory',
      'contact',
      'company',
      'other',
    ]);
  });
});

describe('node style', () => {
  it('colours rules by their group and gives every shape a path', () => {
    expect(nodeStyle('rule', 'block').tone).toBe('danger');
    expect(nodeStyle('rule', 'require_approval').tone).toBe('warning');
    expect(nodeStyle('contact').tone).toBe('neutral');
    for (const shape of ['circle', 'square', 'diamond', 'hexagon', 'triangle'] as const) {
      expect(shapePath(shape, 8)).toMatch(/^M.+Z$/);
    }
  });
});

describe('layout', () => {
  const radii = new Map(nodes.map((n) => [n.id, 8]));
  const graph = sanitizeGraph({ nodes, edges });

  it('is deterministic and finite, and gives every node a position', () => {
    const first = computeLayout(graph.nodes, graph.edges, radii);
    const second = computeLayout(graph.nodes, graph.edges, radii);
    expect(first.size).toBe(graph.nodes.length);
    expect(second).toEqual(first);
    for (const p of first.values()) {
      expect(Number.isFinite(p.x) && Number.isFinite(p.y)).toBe(true);
    }
  });

  it('keeps nodes from overlapping', () => {
    const positions = [...computeLayout(graph.nodes, graph.edges, radii).values()];
    for (const [i, a] of positions.entries()) {
      for (const b of positions.slice(i + 1)) {
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThan(8);
      }
    }
  });

  it('fits points inside the canvas and centres them', () => {
    const view = fitView(
      [
        { x: -100, y: 0, r: 10 },
        { x: 100, y: 0, r: 10 },
      ],
      { w: 400, h: 300 },
    );
    expect(view.k).toBeGreaterThan(0);
    expect(-110 * view.k + view.x).toBeGreaterThanOrEqual(0);
    expect(110 * view.k + view.x).toBeLessThanOrEqual(400);
    expect(view.x).toBeCloseTo(200);
    expect(view.y).toBeCloseTo(150);
  });

  it('zooms around a fixed screen point and clamps the zoom', () => {
    const view = { x: 10, y: 20, k: 1 };
    const zoomed = zoomAt(view, 2, 100, 100);
    // The graph point under (100, 100) must not move.
    expect((100 - view.x) / view.k).toBeCloseTo((100 - zoomed.x) / zoomed.k);
    expect((100 - view.y) / view.k).toBeCloseTo((100 - zoomed.y) / zoomed.k);
    expect(zoomAt(view, 1000, 0, 0).k).toBe(MAX_ZOOM);
  });
});
