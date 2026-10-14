import type { GraphNode, KnowledgeGraphData } from '../api/knowledge-graph.api';
import { computeDegrees, nodeRadius, nodeType, sanitizeGraph } from './graph';
import type { Graph } from './graph';
import { computeLayout } from './layout';
import type { Positions } from './layout';

export interface GraphModel extends Graph {
  byId: Map<string, GraphNode>;
  radii: Map<string, number>;
  /** Settled layout of the whole graph. Filters hide nodes but never move the rest. */
  positions: Positions;
}

/** Everything derived from the payload once: clean graph, node radii by degree and the layout. */
export function buildModel(data: KnowledgeGraphData): GraphModel {
  const graph = sanitizeGraph(data);
  const degrees = computeDegrees(graph.nodes, graph.edges);
  const radii = new Map(
    graph.nodes.map((n) => [n.id, nodeRadius(nodeType(n), degrees.get(n.id) ?? 0)]),
  );
  return {
    ...graph,
    byId: new Map(graph.nodes.map((n) => [n.id, n])),
    radii,
    positions: computeLayout(graph.nodes, graph.edges, radii),
  };
}
