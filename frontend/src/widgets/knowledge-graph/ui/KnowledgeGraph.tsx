import { useMemo, useState } from 'react';
import { AlertCircle, Info, Network, RotateCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/skeleton';
import { useKnowledgeGraph } from '../api/knowledge-graph.api';
import type { KnowledgeGraphData } from '../api/knowledge-graph.api';
import {
  countByType,
  filterGraph,
  groupByType,
  isGraphEmpty,
  matchNodes,
  neighboursOf,
} from '../lib/graph';
import type { NodeType } from '../lib/graph';
import { buildModel } from '../lib/model';
import { GraphCanvas } from './GraphCanvas';
import { GraphPanel } from './GraphPanel';
import { GraphToolbar } from './GraphToolbar';
import { useDisplayLabel } from './use-display-label';

function Explorer({ data }: { data: KnowledgeGraphData }) {
  const { t } = useTranslation('graph');
  const label = useDisplayLabel();
  const model = useMemo(() => buildModel(data), [data]);
  const counts = useMemo(() => countByType(model.nodes), [model]);
  const [hidden, setHidden] = useState<ReadonlySet<NodeType>>(new Set());
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const visible = useMemo(() => filterGraph(model, hidden), [model, hidden]);
  const matches = useMemo(() => matchNodes(visible.nodes, query), [visible, query]);
  // A selection that a filter hides is treated as cleared.
  const selected = visible.nodes.find((n) => n.id === selectedId) ?? null;
  const neighbours = useMemo(
    () => (selected ? neighboursOf(selected.id, visible.edges, model.byId) : []),
    [selected, visible, model],
  );
  const highlight = useMemo(
    () =>
      matches ?? (selected ? new Set([selected.id, ...neighbours.map((n) => n.node.id)]) : null),
    [matches, selected, neighbours],
  );

  const toggleType = (type: NodeType) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (!next.delete(type)) next.add(type);
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <GraphToolbar
        query={query}
        onQueryChange={setQuery}
        matchCount={matches?.size ?? null}
        counts={counts}
        hidden={hidden}
        onToggleType={toggleType}
      />

      {data.truncated && (
        <div className="bg-muted/60 text-muted-foreground flex items-start gap-2.5 rounded-[var(--radius-lg)] border p-3 text-sm">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>{t('truncated')}</p>
        </div>
      )}

      {/* Desktop: panel beside the graph. Mobile: bottom sheet over the graph while a node is selected. */}
      <div className="relative grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <GraphCanvas
          model={model}
          nodes={visible.nodes}
          edges={visible.edges}
          highlight={highlight}
          selectedId={selected?.id ?? null}
          onSelect={setSelectedId}
        />
        <GraphPanel
          node={selected}
          neighbours={neighbours}
          onSelect={setSelectedId}
          onClose={() => {
            setSelectedId(null);
          }}
          className={cn(
            'lg:h-[65vh] lg:min-h-[24rem] lg:overflow-y-auto',
            selected
              ? 'absolute inset-x-2 bottom-2 z-10 max-h-[45%] overflow-y-auto lg:static lg:max-h-none'
              : 'hidden lg:flex',
          )}
        />
      </div>

      {/* Text alternative to the canvas, grouped by type. */}
      <section className="sr-only" aria-label={t('list.title')}>
        {groupByType(visible.nodes).map(([type, list]) => (
          <div key={type}>
            <h2>{t(`types.${type}`)}</h2>
            <ul>
              {list.map((n) => (
                <li key={n.id}>{n.detail ? `${label(n)}: ${n.detail}` : label(n)}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  );
}

function GraphSkeleton() {
  const { t } = useTranslation('common');
  return (
    <div className="flex flex-col gap-4" role="status" aria-busy="true">
      <span className="sr-only">{t('actions.loading')}</span>
      <Skeleton className="h-10 w-full max-w-xs" />
      <div className="flex flex-wrap gap-1.5">
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-8 w-24 rounded-full" />
        ))}
      </div>
      <Skeleton className="h-[65vh] min-h-[24rem] w-full rounded-[var(--radius-lg)]" />
    </div>
  );
}

/** Interactive map of everything the agent knows: memories, organisation facts, rules and business data. */
export function KnowledgeGraph() {
  const { t } = useTranslation('graph');
  const { data, isLoading, isError, refetch } = useKnowledgeGraph();

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">{t('description')}</p>

      {isLoading && <GraphSkeleton />}

      {isError && (
        <div
          role="alert"
          className="bg-card/60 flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border border-dashed px-6 py-10 text-center"
        >
          <span className="bg-danger-bg text-danger-fg flex size-11 items-center justify-center rounded-full">
            <AlertCircle className="size-5" aria-hidden />
          </span>
          <p className="font-medium">{t('error.title')}</p>
          <Button
            variant="outline"
            onClick={() => {
              void refetch();
            }}
          >
            <RotateCw aria-hidden />
            {t('common:actions.retry')}
          </Button>
        </div>
      )}

      {data && isGraphEmpty(data.nodes) && (
        <div className="bg-card/60 flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border border-dashed px-6 py-10 text-center">
          <span className="bg-brand-bg text-brand-ink flex size-11 items-center justify-center rounded-full">
            <Network className="size-5" aria-hidden />
          </span>
          <div className="flex max-w-md flex-col gap-1">
            <p className="font-medium">{t('empty.title')}</p>
            <p className="text-muted-foreground text-sm">{t('empty.description')}</p>
          </div>
          <Button asChild variant="outline">
            <Link to="/app/chat">{t('empty.openChat')}</Link>
          </Button>
        </div>
      )}

      {data && !isGraphEmpty(data.nodes) && <Explorer data={data} />}
    </div>
  );
}
