import { useTranslation } from 'react-i18next';
import type { GraphNode } from '../api/knowledge-graph.api';

/** Label to show for a node: structural nodes arrive as English keys and are translated here. */
export function useDisplayLabel() {
  const { t } = useTranslation('graph');
  return (node: GraphNode): string => {
    if (node.type === 'hub') return t(`hubs.${node.id}`, { defaultValue: node.label });
    if (node.type === 'memory_kind') {
      return t(`brain:kinds.${node.label}`, { defaultValue: node.label });
    }
    return node.label;
  };
}
