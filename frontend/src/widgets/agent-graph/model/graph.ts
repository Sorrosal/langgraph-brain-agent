export interface GraphNode {
  id: string;
  /** Centre of the node in SVG viewBox units. */
  x: number;
  y: number;
  kind: 'node' | 'terminal';
  /** Ids under `landing:agentGraph.nodes.<id>.guarantees`; summaries sit beside them. */
  guarantees: readonly string[];
}

export interface GraphEdge {
  from: string;
  to: string;
  /** Conditional edges are drawn dashed. */
  conditional: boolean;
  points: readonly [number, number, number, number];
}

export const NODE_WIDTH = 140;
export const NODE_HEIGHT = 44;
export const VIEW_BOX = '0 0 800 330';

export const GRAPH_NODES: readonly GraphNode[] = [
  { id: 'load_context', x: 80, y: 50, kind: 'node', guarantees: ['capped', 'degrades'] },
  { id: 'reason', x: 270, y: 50, kind: 'node', guarantees: ['reload', 'maxSteps', 'backoff'] },
  {
    id: 'approval_gate',
    x: 460,
    y: 50,
    kind: 'node',
    guarantees: ['blocked', 'strictest', 'failClosed'],
  },
  {
    id: 'await_approval',
    x: 660,
    y: 50,
    kind: 'node',
    guarantees: ['checkpointed', 'rechecked'],
  },
  {
    id: 'resolve_uncertain',
    x: 660,
    y: 160,
    kind: 'node',
    guarantees: ['choice', 'onlyUncertain'],
  },
  { id: 'tools', x: 460, y: 160, kind: 'node', guarantees: ['replayed', 'atMostOnce'] },
  { id: 'memorize', x: 270, y: 160, kind: 'node', guarantees: ['optional', 'degrades'] },
  { id: 'summarize', x: 270, y: 270, kind: 'node', guarantees: ['overBudget', 'degrades'] },
  { id: 'END', x: 460, y: 270, kind: 'terminal', guarantees: ['persisted'] },
];

export const GRAPH_EDGES: readonly GraphEdge[] = [
  { from: 'load_context', to: 'reason', conditional: false, points: [150, 50, 200, 50] },
  { from: 'reason', to: 'approval_gate', conditional: true, points: [340, 50, 390, 50] },
  { from: 'approval_gate', to: 'await_approval', conditional: true, points: [530, 50, 590, 50] },
  {
    from: 'await_approval',
    to: 'resolve_uncertain',
    conditional: true,
    points: [660, 72, 660, 138],
  },
  {
    from: 'approval_gate',
    to: 'resolve_uncertain',
    conditional: true,
    points: [510, 72, 610, 138],
  },
  { from: 'resolve_uncertain', to: 'tools', conditional: false, points: [590, 160, 530, 160] },
  { from: 'tools', to: 'reason', conditional: true, points: [420, 138, 310, 72] },
  { from: 'reason', to: 'memorize', conditional: true, points: [270, 72, 270, 138] },
  { from: 'memorize', to: 'summarize', conditional: false, points: [270, 182, 270, 248] },
  { from: 'summarize', to: 'END', conditional: false, points: [340, 270, 410, 270] },
];
