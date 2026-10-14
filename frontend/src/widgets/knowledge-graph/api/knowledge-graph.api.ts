import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { api } from '@/shared/api/axios-instance';

/** Optional text: a missing, null or malformed value reads as `undefined` instead of failing the graph. */
const optionalText = z.string().optional().catch(undefined);

/** `type` stays a free string so a node type added by the backend renders with the generic style. */
const nodeSchema = z.object({
  id: z.string(),
  type: z.string(),
  label: z.string().catch(''),
  detail: optionalText,
  group: optionalText,
  created_at: optionalText,
});

const edgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  kind: z.string().catch('has'),
});

export const knowledgeGraphSchema = z.object({
  nodes: z.array(nodeSchema),
  edges: z.array(edgeSchema),
  truncated: z.boolean().catch(false),
});

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  detail?: string | undefined;
  group?: string | undefined;
  created_at?: string | undefined;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: string;
}

export interface KnowledgeGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
}

/** Under `memories` so adding or deleting a memory refreshes the graph with the lists. */
export const knowledgeGraphKey = ['memories', 'graph'] as const;

export function useKnowledgeGraph() {
  return useQuery<KnowledgeGraphData>({
    queryKey: knowledgeGraphKey,
    queryFn: async () => {
      const { data } = await api.get<unknown>('/brain/graph');
      return knowledgeGraphSchema.parse(data);
    },
  });
}
