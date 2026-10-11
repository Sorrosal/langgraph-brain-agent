import { useState } from 'react';
import { cn } from '@/shared/lib/cn';
import {
  GRAPH_EDGES,
  GRAPH_NODES,
  NODE_HEIGHT,
  NODE_WIDTH,
  VIEW_BOX,
  type GraphNode,
} from '../model/graph';

const DEFAULT_NODE_ID = 'reason';

function findNode(id: string): GraphNode {
  return GRAPH_NODES.find((node) => node.id === id) ?? (GRAPH_NODES[0] as GraphNode);
}

export function AgentGraph() {
  const [selectedId, setSelectedId] = useState(DEFAULT_NODE_ID);
  const selected = findNode(selectedId);

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <svg
        viewBox={VIEW_BOX}
        role="group"
        aria-label="Agent graph: load_context, reason, approval_gate, await_approval, resolve_uncertain, tools, memorize, summarize"
        className="bg-card w-full rounded-lg border"
      >
        <defs>
          <marker
            id="graph-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M0 0L10 5L0 10z" className="fill-muted-foreground" />
          </marker>
        </defs>
        {GRAPH_EDGES.map(({ from, to, conditional, points: [x1, y1, x2, y2] }) => {
          const active = from === selectedId || to === selectedId;
          return (
            <line
              key={`${from}-${to}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              markerEnd="url(#graph-arrow)"
              strokeDasharray={conditional ? '5 4' : undefined}
              strokeWidth={active ? 2.5 : 1.5}
              className={cn(
                'stroke-muted-foreground transition-opacity duration-200 motion-reduce:transition-none',
                active ? 'opacity-100' : 'opacity-40',
              )}
            />
          );
        })}
        {GRAPH_NODES.map((node) => {
          const isSelected = node.id === selectedId;
          return (
            <foreignObject
              key={node.id}
              x={node.x - NODE_WIDTH / 2}
              y={node.y - NODE_HEIGHT / 2}
              width={NODE_WIDTH}
              height={NODE_HEIGHT}
            >
              <button
                type="button"
                aria-pressed={isSelected}
                aria-controls="graph-panel"
                onClick={() => {
                  setSelectedId(node.id);
                }}
                onMouseEnter={() => {
                  setSelectedId(node.id);
                }}
                className={cn(
                  'focus-visible:ring-ring h-full w-full border px-1 font-mono text-xs transition-colors duration-200 outline-none focus-visible:ring-2 motion-reduce:transition-none',
                  node.kind === 'terminal' ? 'rounded-full' : 'rounded-md',
                  isSelected
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-secondary text-secondary-foreground hover:bg-accent',
                )}
              >
                {node.id}
              </button>
            </foreignObject>
          );
        })}
      </svg>
      <div
        id="graph-panel"
        role="region"
        aria-live="polite"
        aria-label={`About ${selected.id}`}
        className="bg-card rounded-lg border p-5"
      >
        <h3 className="font-mono text-lg font-semibold">{selected.id}</h3>
        <p className="text-muted-foreground mt-2 text-sm">{selected.summary}</p>
        <h4 className="mt-4 text-sm font-semibold">Guarantees</h4>
        <ul className="text-muted-foreground mt-1 list-disc space-y-1 pl-5 text-sm">
          {selected.guarantees.map((guarantee) => (
            <li key={guarantee}>{guarantee}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
