import { useTranslation } from 'react-i18next';
import { Badge } from '@/shared/ui/badge';
import { Section } from '@/shared/ui/section';
import {
  ARCH_BOX_HEIGHT,
  ARCH_BOX_WIDTH,
  ARCH_BOXES,
  ARCH_DETAIL_MAX_CHARS,
  ARCH_LINKS,
  ARCH_VIEW_BOX,
  STACK_BADGES,
} from '../model/architecture';

/** Greedy word wrap: a detail longer than the box allows continues on the next line. */
function wrap(text: string, maxChars: number): string[] {
  const lines: string[] = [];
  let line = '';
  for (const word of text.split(' ')) {
    if (line && `${line} ${word}`.length > maxChars) {
      lines.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(line);
  return lines;
}

export function Architecture() {
  const { t } = useTranslation('landing');

  return (
    <Section id="architecture" title={t('architecture.title')}>
      {/* The diagram keeps a readable scale and scrolls sideways on narrow screens. */}
      <div
        role="region"
        aria-label={t('architecture.diagram')}
        tabIndex={0}
        className="bg-card shadow-e1 overflow-x-auto rounded-[var(--radius-lg)] border"
      >
        <svg
          viewBox={ARCH_VIEW_BOX}
          role="img"
          aria-label={t('architecture.ariaLabel')}
          className="w-full min-w-[720px]"
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
                className="stroke-muted-foreground opacity-50"
                strokeWidth={1.5}
              />
            );
          })}
          {ARCH_BOXES.map(({ id, x, y }) => {
            const detail = wrap(t(`architecture.boxes.${id}.detail`), ARCH_DETAIL_MAX_CHARS);
            return (
              <g key={id}>
                <rect
                  x={x - ARCH_BOX_WIDTH / 2}
                  y={y - ARCH_BOX_HEIGHT / 2}
                  width={ARCH_BOX_WIDTH}
                  height={ARCH_BOX_HEIGHT}
                  rx={12}
                  className={
                    id === 'runtime' ? 'fill-subtle stroke-brand' : 'fill-subtle stroke-input'
                  }
                  strokeWidth={id === 'runtime' ? 1.5 : 1}
                />
                <text
                  x={x}
                  y={y - 14}
                  textAnchor="middle"
                  className="fill-foreground font-display text-[15px] font-semibold"
                >
                  {t(`architecture.boxes.${id}.title`)}
                </text>
                <text
                  x={x}
                  y={y + 8}
                  textAnchor="middle"
                  className="fill-muted-foreground text-[11px]"
                >
                  {detail.map((line, index) => (
                    <tspan key={line} x={x} dy={index === 0 ? 0 : 15}>
                      {line}
                    </tspan>
                  ))}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <ul className="mt-6 flex flex-wrap gap-2" aria-label={t('architecture.stackLabel')}>
        {STACK_BADGES.map((badge) => (
          <li key={badge}>
            <Badge variant="secondary" className="px-2.5 py-1 text-xs">
              {badge}
            </Badge>
          </li>
        ))}
      </ul>
    </Section>
  );
}
