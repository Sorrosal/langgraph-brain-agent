export interface BrainCard {
  title: string;
  items: readonly string[];
}

export const BRAIN_CARDS: readonly BrainCard[] = [
  {
    title: 'Long-term memory',
    items: [
      'Facts, preferences and episodes kept in a PostgreSQL store',
      'Semantic recall through pgvector',
      'Recalled at the start of a turn, extracted at the end',
    ],
  },
  {
    title: 'Rules',
    items: [
      'Persona and guidelines in a YAML rule set',
      'Hard rules: block or require approval',
      'Hot reload; invalid rules fail closed',
    ],
  },
  {
    title: 'Context budget',
    items: [
      'The prompt is assembled within a size budget',
      'Old messages are folded into a running summary',
      'Summarization only runs when the history is over budget',
    ],
  },
];
