import { Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/shared/lib/cn';
import { Input } from '@/shared/ui/input';
import { ALL_TYPES, FILTER_TYPES } from '../lib/graph';
import type { NodeType } from '../lib/graph';
import { NodeGlyph } from './NodeGlyph';

interface GraphToolbarProps {
  query: string;
  onQueryChange: (query: string) => void;
  /** Number of search hits, or `null` while the search box is empty. */
  matchCount: number | null;
  counts: ReadonlyMap<NodeType, number>;
  hidden: ReadonlySet<NodeType>;
  onToggleType: (type: NodeType) => void;
}

function EdgeSample({ dashed }: { dashed?: boolean }) {
  return (
    <svg viewBox="0 0 24 6" aria-hidden focusable="false" className="h-1.5 w-6 shrink-0">
      <line
        x1="1"
        y1="3"
        x2="23"
        y2="3"
        stroke={dashed ? 'var(--c-brand)' : 'var(--c-border-strong)'}
        strokeWidth="1.5"
        strokeDasharray={dashed ? '4 3' : undefined}
      />
    </svg>
  );
}

/** Search, type filters (with counts), the stats line and a legend. */
export function GraphToolbar({
  query,
  onQueryChange,
  matchCount,
  counts,
  hidden,
  onToggleType,
}: GraphToolbarProps) {
  const { t } = useTranslation('graph');
  const count = (type: NodeType) => counts.get(type) ?? 0;
  const stats = FILTER_TYPES.filter((type) => type !== 'other' && count(type) > 0).map((type) =>
    t(`stats.${type}`, { count: count(type) }),
  );
  const legendTypes = ALL_TYPES.filter((type) => count(type) > 0 && type !== 'rule');

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search
            className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
            aria-hidden
          />
          <Input
            type="search"
            value={query}
            onChange={(e) => {
              onQueryChange(e.target.value);
            }}
            placeholder={t('search.placeholder')}
            aria-label={t('search.label')}
            className="pl-9"
          />
        </div>
        <p className="text-muted-foreground text-xs" aria-live="polite">
          {matchCount === null
            ? stats.join(' · ')
            : matchCount === 0
              ? t('search.none')
              : t('search.results', { count: matchCount })}
        </p>
      </div>

      <div role="group" aria-label={t('filters.label')} className="flex flex-wrap gap-1.5">
        {FILTER_TYPES.filter((type) => count(type) > 0).map((type) => {
          const active = !hidden.has(type);
          return (
            <button
              key={type}
              type="button"
              aria-pressed={active}
              onClick={() => {
                onToggleType(type);
              }}
              className={cn(
                'focus-visible:ring-ring inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none',
                active
                  ? 'bg-elevated border-input text-foreground shadow-e1 hover:bg-subtle'
                  : 'text-muted-foreground hover:text-foreground border-dashed opacity-70',
              )}
            >
              <NodeGlyph type={type} />
              {t(`types.${type}`)}
              <span className="text-muted-foreground tabular-nums">{count(type)}</span>
            </button>
          );
        })}
      </div>

      <details className="text-muted-foreground text-xs">
        <summary className="hover:text-foreground focus-visible:ring-ring w-fit cursor-pointer rounded-sm select-none focus-visible:ring-2 focus-visible:outline-none">
          {t('legend.title')}
        </summary>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5">
          {legendTypes.map((type) => (
            <li key={type} className="flex items-center gap-1.5">
              <NodeGlyph type={type} />
              {t(`types.${type}`)}
            </li>
          ))}
          {count('rule') > 0 && (
            <>
              <li className="flex items-center gap-1.5">
                <NodeGlyph type="rule" group="require_approval" />
                {t('legend.ruleApproval')}
              </li>
              <li className="flex items-center gap-1.5">
                <NodeGlyph type="rule" group="block" />
                {t('legend.ruleBlock')}
              </li>
            </>
          )}
          <li className="flex items-center gap-1.5">
            <EdgeSample />
            {t('legend.link')}
          </li>
          <li className="flex items-center gap-1.5">
            <EdgeSample dashed />
            {t('legend.mention')}
          </li>
        </ul>
      </details>
    </div>
  );
}
