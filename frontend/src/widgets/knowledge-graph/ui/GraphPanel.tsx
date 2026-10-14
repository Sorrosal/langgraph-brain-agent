import { MousePointerClick, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/shared/lib/cn';
import { formatDate, formatRelativeTime } from '@/shared/lib/format';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import type { GraphNode } from '../api/knowledge-graph.api';
import { nodeType } from '../lib/graph';
import type { Neighbour } from '../lib/graph';
import { nodeStyle } from '../lib/node-style';
import type { Tone } from '../lib/node-style';
import { NodeGlyph } from './NodeGlyph';
import { useDisplayLabel } from './use-display-label';

const TONE_BADGE = {
  brand: 'default',
  info: 'info',
  warning: 'warning',
  danger: 'destructive',
  success: 'success',
  neutral: 'secondary',
} as const satisfies Record<Tone, string>;

interface GraphPanelProps {
  node: GraphNode | null;
  neighbours: readonly Neighbour[];
  onSelect: (id: string) => void;
  onClose: () => void;
  className?: string;
}

/** Details of the selected node and its connections. Placeholder when nothing is selected. */
export function GraphPanel({ node, neighbours, onSelect, onClose, className }: GraphPanelProps) {
  const { t } = useTranslation('graph');
  const label = useDisplayLabel();
  const relationTitle = (other: GraphNode, kind: string) =>
    [t(`types.${nodeType(other)}`), t(`relations.${kind}`, { defaultValue: kind })].join(' · ');

  return (
    <aside
      aria-label={t('panel.label')}
      className={cn(
        'bg-card shadow-e2 flex flex-col gap-3 rounded-[var(--radius-lg)] border p-4',
        className,
      )}
    >
      {node ? (
        <>
          <div className="flex items-start justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant={TONE_BADGE[nodeStyle(nodeType(node), node.group).tone]}>
                <NodeGlyph type={nodeType(node)} group={node.group} />
                {t(`types.${nodeType(node)}`)}
              </Badge>
              {node.group && (
                <Badge variant="outline">
                  {t(`groups.${node.group}`, { defaultValue: node.group })}
                </Badge>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="-mt-1 -mr-1 size-8 shrink-0"
              aria-label={t('panel.close')}
              onClick={onClose}
            >
              <X aria-hidden />
            </Button>
          </div>

          <h3 className="text-base font-semibold break-words">{label(node)}</h3>
          {node.detail && (
            <p className="text-reading text-foreground/90 break-words whitespace-pre-wrap">
              {node.detail}
            </p>
          )}
          {node.created_at && (
            <time
              dateTime={node.created_at}
              title={formatDate(node.created_at, { dateStyle: 'medium', timeStyle: 'short' })}
              className="text-muted-foreground text-xs"
            >
              {t('panel.added', { when: formatRelativeTime(node.created_at) })}
            </time>
          )}

          <section className="flex flex-col gap-2 border-t pt-3" aria-labelledby="kg-connections">
            <h4 id="kg-connections" className="text-muted-foreground text-xs font-semibold">
              {t('panel.connections', { count: neighbours.length })}
            </h4>
            {neighbours.length === 0 ? (
              <p className="text-muted-foreground text-sm">{t('panel.noConnections')}</p>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {neighbours.map(({ node: other, kind }) => (
                  <li key={other.id}>
                    <button
                      type="button"
                      title={relationTitle(other, kind)}
                      onClick={() => {
                        onSelect(other.id);
                      }}
                      className="bg-elevated hover:bg-subtle focus-visible:ring-ring inline-flex h-8 max-w-full items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
                    >
                      <NodeGlyph type={nodeType(other)} group={other.group} />
                      <span className="truncate">{label(other)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : (
        <div className="text-muted-foreground flex flex-col items-center gap-2 py-6 text-center text-sm">
          <MousePointerClick className="size-5" aria-hidden />
          <p>{t('panel.empty')}</p>
        </div>
      )}
    </aside>
  );
}
