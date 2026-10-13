import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/shared/lib/cn';
import { Card } from '@/shared/ui/card';
import {
  GRAPH_EDGES,
  GRAPH_NODES,
  NODE_HEIGHT,
  NODE_WIDTH,
  VIEW_BOX,
  type GraphNode,
} from '../model/graph';

const DEFAULT_NODE_ID = 'reason';
const NODE_IDS = GRAPH_NODES.map((node) => node.id).join(', ');

function findNode(id: string): GraphNode {
  return GRAPH_NODES.find((node) => node.id === id) ?? (GRAPH_NODES[0] as GraphNode);
}

export function AgentGraph() {
  const { t } = useTranslation('landing');
  const [selectedId, setSelectedId] = useState(DEFAULT_NODE_ID);
  const selected = findNode(selectedId);

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      {/* Below `lg` the graph keeps its natural size (44px nodes) and scrolls sideways. */}
      <div className="bg-card shadow-e1 self-start overflow-x-auto rounded-[var(--radius-lg)] border">
        <svg
          viewBox={VIEW_BOX}
          role="group"
          aria-label={t('agentGraph.ariaLabel', { nodes: NODE_IDS })}
          className="w-full min-w-[800px] lg:min-w-0"
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
                    'focus-visible:ring-ring h-full w-full border px-1 font-mono text-xs transition-colors duration-200 outline-none focus-visible:ring-2 focus-visible:ring-inset motion-reduce:transition-none',
                    node.kind === 'terminal' ? 'rounded-full' : 'rounded-[var(--radius-md)]',
                    isSelected
                      ? 'bg-primary text-primary-foreground border-primary shadow-primary'
                      : 'bg-subtle text-foreground border-input hover:bg-accent hover:text-accent-foreground',
                  )}
                >
                  {node.id}
                </button>
              </foreignObject>
            );
          })}
        </svg>
      </div>
      <Card
        id="graph-panel"
        role="region"
        aria-live="polite"
        aria-label={t('agentGraph.about', { node: selected.id })}
        className="self-start p-5"
      >
        <h3 className="font-mono text-lg font-semibold">{selected.id}</h3>
        <p className="text-muted-foreground mt-2 text-sm">
          {t(`agentGraph.nodes.${selected.id}.summary`)}
        </p>
        <h4 className="mt-4 text-sm font-semibold">{t('agentGraph.guarantees')}</h4>
        <ul className="text-muted-foreground marker:text-faint mt-1.5 list-disc space-y-1.5 pl-5 text-sm">
          {selected.guarantees.map((guarantee) => (
            <li key={guarantee}>{t(`agentGraph.nodes.${selected.id}.guarantees.${guarantee}`)}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
