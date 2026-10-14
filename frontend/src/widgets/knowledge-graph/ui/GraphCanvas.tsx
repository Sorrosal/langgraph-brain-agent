import { useEffect, useId, useRef, useState } from 'react';
import { Maximize2, ZoomIn, ZoomOut } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { truncate } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import type { GraphEdge, GraphNode } from '../api/knowledge-graph.api';
import { edgeKey, isStructural, nodeType } from '../lib/graph';
import { fitView, zoomAt } from '../lib/layout';
import type { Point, Positions, View } from '../lib/layout';
import type { GraphModel } from '../lib/model';
import { nodeStyle, PRISM_STOPS, shapePath, TONE_COLORS } from '../lib/node-style';
import { useDisplayLabel } from './use-display-label';

interface GraphCanvasProps {
  model: GraphModel;
  /** Nodes and edges that survive the type filters. */
  nodes: readonly GraphNode[];
  edges: readonly GraphEdge[];
  /** Nodes to keep at full strength (search hits or the selection and its neighbours). */
  highlight: ReadonlySet<string> | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

type Gesture =
  | {
      kind: 'node';
      id: string;
      pointerId: number;
      startX: number;
      startY: number;
      moved: boolean;
      /** Pointer-to-node offset in graph space, so the node does not jump under the cursor. */
      dx: number;
      dy: number;
    }
  | {
      kind: 'pan';
      pointerId: number;
      startX: number;
      startY: number;
      moved: boolean;
      origX: number;
      origY: number;
    };

const DRAG_THRESHOLD = 4;
const FALLBACK_SIZE = { w: 800, h: 520 };
/** Zoom level from which every label is drawn. */
const LABELS_FROM_ZOOM = 1.8;
/** A search with more hits than this would drown the canvas in labels. */
const MAX_HIGHLIGHT_LABELS = 25;

const at = (p: Point) => `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`;

function pointsOf(nodes: readonly GraphNode[], pos: Positions, radii: ReadonlyMap<string, number>) {
  return nodes.flatMap((n) => {
    const p = pos.get(n.id);
    return p ? [{ ...p, r: radii.get(n.id) ?? 6 }] : [];
  });
}

/**
 * SVG canvas: pan (drag the background or use the wheel), zoom, drag nodes, select. The layout
 * is settled before the first paint; dragging moves only the grabbed node.
 */
export function GraphCanvas({
  model,
  nodes,
  edges,
  highlight,
  selectedId,
  onSelect,
}: GraphCanvasProps) {
  const { t } = useTranslation('graph');
  const label = useDisplayLabel();
  const titleId = useId();
  const descId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const gesture = useRef<Gesture | null>(null);

  const [size, setSize] = useState(FALLBACK_SIZE);
  const [view, setView] = useState<View>({ x: FALLBACK_SIZE.w / 2, y: FALLBACK_SIZE.h / 2, k: 1 });
  // Positions start from the settled layout and diverge only where the user drags a node.
  const [pos, setPos] = useState<Positions>(() => new Map(model.positions));
  const [layoutSeen, setLayoutSeen] = useState(model.positions);
  if (layoutSeen !== model.positions) {
    setLayoutSeen(model.positions);
    setPos(new Map(model.positions));
  }
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setSize({ w: entry.contentRect.width, h: entry.contentRect.height });
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
    };
  }, []);

  // Fit the whole graph when it (re)loads, and on resize until the user pans or zooms by hand
  // (a mobile address bar collapsing resizes the canvas mid-gesture).
  const touched = useRef(false);
  const fittedModel = useRef(model);
  useEffect(() => {
    if (fittedModel.current !== model) {
      fittedModel.current = model;
      touched.current = false;
    }
    if (!touched.current) {
      setView(fitView(pointsOf(model.nodes, model.positions, model.radii), size));
    }
  }, [model, size]);

  // React attaches wheel listeners as passive; zooming has to cancel the page scroll.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      touched.current = true;
      const rect = svg.getBoundingClientRect();
      const delta = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      const factor = Math.exp(-delta * 0.0015);
      setView((v) => zoomAt(v, factor, e.clientX - rect.left, e.clientY - rect.top));
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      svg.removeEventListener('wheel', onWheel);
    };
  }, []);

  // Bring a node selected from the side panel into view if it is off-canvas.
  const live = useRef({ view, pos, size });
  useEffect(() => {
    live.current = { view, pos, size };
  });
  useEffect(() => {
    if (!selectedId) return;
    const { view: v, pos: positions, size: s } = live.current;
    const p = positions.get(selectedId);
    if (!p) return;
    const sx = p.x * v.k + v.x;
    const sy = p.y * v.k + v.y;
    const margin = 48;
    if (sx < margin || sy < margin || sx > s.w - margin || sy > s.h - margin) {
      setView({ k: v.k, x: s.w / 2 - p.x * v.k, y: s.h / 2 - p.y * v.k });
    }
  }, [selectedId]);

  const toGraph = (e: { clientX: number; clientY: number }): Point => {
    const rect = svgRef.current?.getBoundingClientRect();
    return {
      x: (e.clientX - (rect?.left ?? 0) - view.x) / view.k,
      y: (e.clientY - (rect?.top ?? 0) - view.y) / view.k,
    };
  };

  const onNodeDown = (e: React.PointerEvent<SVGGElement>, id: string) => {
    const p = pos.get(id);
    if (e.button !== 0 || gesture.current || !p) return;
    e.stopPropagation();
    const g = toGraph(e);
    svgRef.current?.setPointerCapture(e.pointerId);
    gesture.current = {
      kind: 'node',
      id,
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      moved: false,
      dx: g.x - p.x,
      dy: g.y - p.y,
    };
  };

  const onBackgroundDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0 || gesture.current) return;
    svgRef.current?.setPointerCapture(e.pointerId);
    gesture.current = {
      kind: 'pan',
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      moved: false,
      origX: view.x,
      origY: view.y,
    };
  };

  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const g = gesture.current;
    if (g?.pointerId !== e.pointerId) return;
    const dx = e.clientX - g.startX;
    const dy = e.clientY - g.startY;
    if (!g.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    g.moved = true;
    touched.current = true;
    if (g.kind === 'node') {
      const p = toGraph(e);
      setPos((prev) => new Map(prev).set(g.id, { x: p.x - g.dx, y: p.y - g.dy }));
    } else {
      setView((v) => ({ ...v, x: g.origX + dx, y: g.origY + dy }));
    }
  };

  const endGesture = (e: React.PointerEvent<SVGSVGElement>, cancelled: boolean) => {
    const g = gesture.current;
    if (g?.pointerId !== e.pointerId) return;
    gesture.current = null;
    svgRef.current?.releasePointerCapture(e.pointerId);
    // A tap, not a drag: select the node, or clear the selection on the background.
    if (!cancelled && !g.moved) onSelect(g.kind === 'node' ? g.id : null);
  };

  const zoomBy = (factor: number) => {
    touched.current = true;
    setView((v) => zoomAt(v, factor, size.w / 2, size.h / 2));
  };

  const fit = () => {
    touched.current = false;
    setView(fitView(pointsOf(nodes, pos, model.radii), size));
  };

  const showAllLabels = highlight === null && view.k >= LABELS_FROM_ZOOM;
  const showLabel = (n: GraphNode) =>
    isStructural(nodeType(n)) ||
    n.id === hoverId ||
    n.id === focusId ||
    n.id === selectedId ||
    showAllLabels ||
    (highlight !== null && highlight.size <= MAX_HIGHLIGHT_LABELS && highlight.has(n.id));
  const fade = (id: string) => (highlight && !highlight.has(id) ? 'opacity-[0.18]' : '');

  return (
    <div
      ref={wrapRef}
      className="bg-card/60 shadow-e1 relative h-[65vh] min-h-[24rem] overflow-hidden rounded-[var(--radius-lg)] border [background-image:radial-gradient(var(--c-border-strong)_1px,transparent_1px)] [background-size:22px_22px]"
    >
      <svg
        ref={svgRef}
        role="group"
        aria-labelledby={titleId}
        aria-describedby={descId}
        className="absolute inset-0 size-full cursor-grab touch-none select-none active:cursor-grabbing"
        onPointerDown={onBackgroundDown}
        onPointerMove={onPointerMove}
        onPointerUp={(e) => {
          endGesture(e, false);
        }}
        onPointerCancel={(e) => {
          endGesture(e, true);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onSelect(null);
        }}
      >
        <title id={titleId}>{t('canvas.title')}</title>
        <desc id={descId}>
          {t('canvas.description', { nodes: nodes.length, edges: edges.length })}
        </desc>
        <defs>
          <linearGradient id="kg-prism" x1="0" y1="0" x2="1" y2="1">
            {PRISM_STOPS.map((color, i) => (
              <stop key={color} offset={i / (PRISM_STOPS.length - 1)} stopColor={color} />
            ))}
          </linearGradient>
          <radialGradient id="kg-gloss" cx="0.3" cy="0.22" r="0.45">
            <stop offset="0" stopColor="white" stopOpacity="0.85" />
            <stop offset="1" stopColor="white" stopOpacity="0" />
          </radialGradient>
        </defs>

        <g transform={`${at(view)} scale(${view.k.toFixed(3)})`}>
          <g aria-hidden>
            {edges.map((e) => {
              const a = pos.get(e.source);
              const b = pos.get(e.target);
              if (!a || !b) return null;
              const mention = e.kind === 'mentions';
              const dim = highlight && !(highlight.has(e.source) && highlight.has(e.target));
              return (
                <line
                  key={edgeKey(e)}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={mention ? 'var(--c-brand)' : 'var(--c-border-strong)'}
                  strokeOpacity={mention ? 0.55 : 1}
                  strokeWidth={1}
                  strokeDasharray={mention ? '5 4' : undefined}
                  vectorEffect="non-scaling-stroke"
                  className={dim ? 'opacity-15' : ''}
                />
              );
            })}
          </g>

          {nodes.map((n) => {
            const p = pos.get(n.id);
            if (!p) return null;
            const type = nodeType(n);
            const style = nodeStyle(type, n.group);
            const colors = TONE_COLORS[style.tone];
            const r = model.radii.get(n.id) ?? 6;
            const selected = n.id === selectedId;
            return (
              <g
                key={n.id}
                transform={at(p)}
                role="button"
                tabIndex={0}
                aria-label={`${t(`types.${type}`)}: ${label(n)}`}
                aria-pressed={selected}
                className={`cursor-pointer transition-opacity duration-150 outline-none ${fade(n.id)}`}
                onPointerDown={(e) => {
                  onNodeDown(e, n.id);
                }}
                onPointerEnter={() => {
                  setHoverId(n.id);
                }}
                onPointerLeave={() => {
                  setHoverId((id) => (id === n.id ? null : id));
                }}
                onFocus={() => {
                  setFocusId(n.id);
                }}
                onBlur={() => {
                  setFocusId((id) => (id === n.id ? null : id));
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect(n.id);
                  }
                }}
              >
                {/* Generous invisible hit area: nodes are tiny on a phone. */}
                <circle r={r + 7} fill="transparent" />
                {(selected || n.id === focusId) && (
                  <circle
                    r={r + 5}
                    fill="none"
                    stroke="var(--c-ring)"
                    strokeWidth={2.5}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                {type === 'user' ? (
                  <>
                    <circle r={r} fill="url(#kg-prism)" />
                    <circle r={r} fill="url(#kg-gloss)" />
                  </>
                ) : (
                  <path
                    d={shapePath(style.shape, r)}
                    fill={style.ring ? colors.soft : colors.solid}
                    stroke={style.ring ? colors.solid : 'var(--c-bg)'}
                    strokeWidth={style.ring ? 2 : 1.5}
                    strokeLinejoin="round"
                    vectorEffect="non-scaling-stroke"
                  />
                )}
              </g>
            );
          })}

          {/* Labels sit above every node so a neighbour never hides them. */}
          <g aria-hidden pointerEvents="none">
            {nodes.map((n) => {
              const p = pos.get(n.id);
              if (!p || !showLabel(n)) return null;
              const structural = isStructural(nodeType(n));
              return (
                <text
                  key={n.id}
                  x={p.x}
                  y={p.y + (model.radii.get(n.id) ?? 6) + 13 / view.k}
                  textAnchor="middle"
                  fontSize={(structural ? 12 : 11) / view.k}
                  fontWeight={structural ? 600 : 500}
                  fill="var(--c-fg)"
                  stroke="var(--c-bg)"
                  strokeWidth={3.5 / view.k}
                  strokeLinejoin="round"
                  paintOrder="stroke"
                  className={fade(n.id)}
                >
                  {truncate(label(n), 32)}
                </text>
              );
            })}
          </g>
        </g>
      </svg>

      <div className="absolute top-3 right-3 flex flex-col gap-1.5">
        <Button
          variant="outline"
          size="icon"
          className="size-9"
          aria-label={t('zoom.in')}
          onClick={() => {
            zoomBy(1.3);
          }}
        >
          <ZoomIn aria-hidden />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="size-9"
          aria-label={t('zoom.out')}
          onClick={() => {
            zoomBy(1 / 1.3);
          }}
        >
          <ZoomOut aria-hidden />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="size-9"
          aria-label={t('zoom.fit')}
          onClick={fit}
        >
          <Maximize2 aria-hidden />
        </Button>
      </div>
    </div>
  );
}
