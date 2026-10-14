import type { GraphEdge, GraphNode, KnowledgeGraphData } from '../api/knowledge-graph.api';

const KNOWN_TYPES = [
  'user',
  'hub',
  'memory_kind',
  'memory',
  'org',
  'rule',
  'guideline',
  'tool',
  'company',
  'contact',
  'deal',
  'task',
] as const;

/** `other` is any type the UI does not know yet; it gets the generic style. */
export type NodeType = (typeof KNOWN_TYPES)[number] | 'other';

/** Structural nodes that give the graph its shape; they are never filtered out. */
const STRUCTURAL: readonly NodeType[] = ['user', 'hub', 'memory_kind'];

/** Filter chips, in display order. */
export const FILTER_TYPES: readonly NodeType[] = [
  'memory',
  'org',
  'rule',
  'guideline',
  'tool',
  'contact',
  'company',
  'deal',
  'task',
  'other',
];

/** Legend and screen-reader list order. */
export const ALL_TYPES: readonly NodeType[] = [...STRUCTURAL, ...FILTER_TYPES];

export function nodeType(node: Pick<GraphNode, 'type'>): NodeType {
  return (KNOWN_TYPES as readonly string[]).includes(node.type) ? (node.type as NodeType) : 'other';
}

export function isStructural(type: NodeType): boolean {
  return STRUCTURAL.includes(type);
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Drops duplicate nodes and edges, self-loops and edges to a missing node, so layout never throws. */
export function sanitizeGraph(data: Pick<KnowledgeGraphData, 'nodes' | 'edges'>): Graph {
  const byId = new Map<string, GraphNode>();
  for (const node of data.nodes) if (!byId.has(node.id)) byId.set(node.id, node);
  const seen = new Set<string>();
  const edges = data.edges.filter((e) => {
    const key = JSON.stringify([e.source, e.target, e.kind]);
    if (e.source === e.target || !byId.has(e.source) || !byId.has(e.target) || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
  return { nodes: [...byId.values()], edges };
}

/** Stable React key of an edge (unique after `sanitizeGraph`). */
export function edgeKey(e: GraphEdge): string {
  return JSON.stringify([e.source, e.target, e.kind]);
}

export function computeDegrees(nodes: readonly GraphNode[], edges: readonly GraphEdge[]) {
  const degrees = new Map<string, number>(nodes.map((n) => [n.id, 0]));
  for (const e of edges) {
    degrees.set(e.source, (degrees.get(e.source) ?? 0) + 1);
    degrees.set(e.target, (degrees.get(e.target) ?? 0) + 1);
  }
  return degrees;
}

const BASE_RADIUS: Record<NodeType, number> = {
  user: 22,
  hub: 15,
  memory_kind: 13,
  memory: 6,
  org: 6,
  rule: 7,
  guideline: 6,
  tool: 5,
  company: 7,
  contact: 6,
  deal: 6,
  task: 6,
  other: 6,
};

/** Node radius grows with its number of connections, capped so hubs do not swallow the canvas. */
export function nodeRadius(type: NodeType, degree: number): number {
  return BASE_RADIUS[type] + Math.min(9, Math.sqrt(degree) * 1.8);
}

export function countByType(nodes: readonly GraphNode[]): Map<NodeType, number> {
  const counts = new Map<NodeType, number>();
  for (const node of nodes) {
    const type = nodeType(node);
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }
  return counts;
}

/** True when there is nothing to explore yet: no node beyond the user, hubs and memory kinds. */
export function isGraphEmpty(nodes: readonly GraphNode[]): boolean {
  return nodes.every((n) => isStructural(nodeType(n)));
}

/** Hides the types in `hidden` and every edge that touches a hidden node. Structural nodes stay. */
export function filterGraph(graph: Graph, hidden: ReadonlySet<NodeType>): Graph {
  if (hidden.size === 0) return graph;
  const nodes = graph.nodes.filter((n) => !hidden.has(nodeType(n)));
  const ids = new Set(nodes.map((n) => n.id));
  return { nodes, edges: graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) };
}

/** Ids of the nodes whose label or detail contains the query; `null` when the query is blank. */
export function matchNodes(nodes: readonly GraphNode[], query: string): Set<string> | null {
  const q = query.trim().toLocaleLowerCase();
  if (!q) return null;
  const ids = new Set<string>();
  for (const n of nodes) {
    if (`${n.label}\n${n.detail ?? ''}`.toLocaleLowerCase().includes(q)) ids.add(n.id);
  }
  return ids;
}

export interface Neighbour {
  node: GraphNode;
  kind: string;
}

/** Nodes directly connected to `id` (either direction), in first-seen order, without repeats. */
export function neighboursOf(
  id: string,
  edges: readonly GraphEdge[],
  byId: ReadonlyMap<string, GraphNode>,
): Neighbour[] {
  const seen = new Set<string>();
  const result: Neighbour[] = [];
  for (const e of edges) {
    const otherId = e.source === id ? e.target : e.target === id ? e.source : null;
    if (otherId === null || seen.has(otherId)) continue;
    const node = byId.get(otherId);
    if (!node) continue;
    seen.add(otherId);
    result.push({ node, kind: e.kind });
  }
  return result;
}

/** Group nodes by type in legend order, dropping empty groups. */
export function groupByType(nodes: readonly GraphNode[]): [NodeType, GraphNode[]][] {
  const groups = new Map<NodeType, GraphNode[]>();
  for (const node of nodes) {
    const type = nodeType(node);
    const list = groups.get(type);
    if (list) list.push(node);
    else groups.set(type, [node]);
  }
  return ALL_TYPES.flatMap((type) => {
    const list = groups.get(type);
    return list ? [[type, list] as [NodeType, GraphNode[]]] : [];
  });
}
