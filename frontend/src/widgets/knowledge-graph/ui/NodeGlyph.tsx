import { cn } from '@/shared/lib/cn';
import type { NodeType } from '../lib/graph';
import { nodeStyle, shapePath, TONE_COLORS } from '../lib/node-style';

/** Small swatch of a node's shape and colour, for chips, legend and the side panel. */
export function NodeGlyph({
  type,
  group,
  className,
}: {
  type: NodeType;
  group?: string | undefined;
  className?: string;
}) {
  if (type === 'user') {
    return <span aria-hidden className={cn('ev-orb inline-block size-3.5 shrink-0', className)} />;
  }
  const style = nodeStyle(type, group);
  const colors = TONE_COLORS[style.tone];
  return (
    <svg
      viewBox="-11 -11 22 22"
      aria-hidden
      focusable="false"
      className={cn('size-3.5 shrink-0', className)}
    >
      <path
        d={shapePath(style.shape, 7)}
        fill={style.ring ? colors.soft : colors.solid}
        stroke={colors.solid}
        strokeWidth={2}
        strokeLinejoin="round"
      />
    </svg>
  );
}
