import { Badge } from '@/shared/ui/badge';
import { Section } from '@/shared/ui/section';
import {
  ARCH_BOX_HEIGHT,
  ARCH_BOX_WIDTH,
  ARCH_BOXES,
  ARCH_LINKS,
  ARCH_VIEW_BOX,
  STACK_BADGES,
} from '../model/architecture';

export function Architecture() {
  return (
    <Section id="architecture" title="Architecture & stack">
      <svg
        viewBox={ARCH_VIEW_BOX}
        role="img"
        aria-label="Architecture: the React UI talks to FastAPI, which drives the LangGraph runtime. The runtime uses PostgreSQL for checkpoints, memory, runs and the tool ledger, and OpenAI for models."
        className="bg-card w-full rounded-lg border"
      >
        {ARCH_LINKS.map(([from, to]) => {
          const a = ARCH_BOXES.find((box) => box.id === from);
          const b = ARCH_BOXES.find((box) => box.id === to);
          if (!a || !b) return null;
          return (
            <line
              key={`${from}-${to}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              className="stroke-muted-foreground"
              strokeWidth={1.5}
            />
          );
        })}
        {ARCH_BOXES.map(({ id, title, detail, x, y }) => (
          <g key={id}>
            <rect
              x={x - ARCH_BOX_WIDTH / 2}
              y={y - ARCH_BOX_HEIGHT / 2}
              width={ARCH_BOX_WIDTH}
              height={ARCH_BOX_HEIGHT}
              rx={8}
              className="fill-secondary stroke-border"
            />
            <text
              x={x}
              y={y - 6}
              textAnchor="middle"
              className="fill-foreground text-[15px] font-semibold"
            >
              {title}
            </text>
            <text
              x={x}
              y={y + 14}
              textAnchor="middle"
              className="fill-muted-foreground text-[10px]"
            >
              {detail}
            </text>
          </g>
        ))}
      </svg>
      <ul className="mt-6 flex flex-wrap gap-2" aria-label="Technology stack">
        {STACK_BADGES.map((badge) => (
          <li key={badge}>
            <Badge variant="secondary">{badge}</Badge>
          </li>
        ))}
      </ul>
    </Section>
  );
}
