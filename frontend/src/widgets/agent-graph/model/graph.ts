export interface GraphNode {
  id: string;
  /** Centre of the node in SVG viewBox units. */
  x: number;
  y: number;
  kind: 'node' | 'terminal';
  summary: string;
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
  {
    id: 'load_context',
    x: 80,
    y: 50,
    kind: 'node',
    summary:
      'At the start of each user turn, recalls the most relevant long-term memories (semantic search over the store) and adds them to the model context.',
    guarantees: ['Recall is capped (5 memories by default)', 'Failures degrade to a no-op'],
  },
  {
    id: 'reason',
    x: 270,
    y: 50,
    kind: 'node',
    summary:
      'Calls the model with a system prompt rebuilt from the rule set on every call. If the model asks for tools the run goes to the approval gate; otherwise the turn ends.',
    guarantees: [
      'Rule reloads apply on the next call',
      'Bounded by a max-steps limit (25 by default)',
      'Transient errors retried with exponential backoff',
    ],
  },
  {
    id: 'approval_gate',
    x: 460,
    y: 50,
    kind: 'node',
    summary:
      'Checks every tool call against the approval policy: tool metadata plus the hard rules. Calls that violate a block rule are refused; calls that require approval are marked for review.',
    guarantees: [
      'Blocked calls are never executed',
      'The strictest verdict wins',
      'Rules fail closed',
    ],
  },
  {
    id: 'await_approval',
    x: 660,
    y: 50,
    kind: 'node',
    summary:
      'Pauses the graph with a LangGraph interrupt() until a human approves, edits, rejects or responds to each pending call.',
    guarantees: [
      'The pause is checkpointed in PostgreSQL, so it survives restarts',
      'Edited calls are re-checked against block rules',
    ],
  },
  {
    id: 'resolve_uncertain',
    x: 660,
    y: 160,
    kind: 'node',
    summary:
      'Before tools run, asks a human about calls whose earlier execution has an unknown outcome (recorded as started in the tool ledger, but never finished).',
    guarantees: [
      'The human chooses: confirm done, retry or skip',
      'Only calls that are still uncertain are asked about',
    ],
  },
  {
    id: 'tools',
    x: 460,
    y: 160,
    kind: 'node',
    summary:
      'Executes the approved tool calls through the tool ledger, keyed by thread id and tool call id, then hands the results back to the model.',
    guarantees: [
      'Succeeded calls are replayed from the ledger, not re-run',
      'Side effects happen at most once unless a human authorizes a retry',
    ],
  },
  {
    id: 'memorize',
    x: 270,
    y: 160,
    kind: 'node',
    summary:
      'At the end of a turn, asks the model to extract durable facts and preferences and writes them to the long-term store.',
    guarantees: ['Optional (memory extraction flag)', 'Failures degrade to a no-op'],
  },
  {
    id: 'summarize',
    x: 270,
    y: 270,
    kind: 'node',
    summary:
      'When the history exceeds the context budget, folds the oldest messages into a running summary so the prompt stays within bounds.',
    guarantees: ['Only runs over budget', 'Failures degrade to a no-op'],
  },
  {
    id: 'END',
    x: 460,
    y: 270,
    kind: 'terminal',
    summary:
      'The turn is finished. The final state stays checkpointed and the thread can continue.',
    guarantees: ['Every step before this point was persisted'],
  },
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
