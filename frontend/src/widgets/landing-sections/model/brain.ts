export interface BrainCard {
  id: 'memory' | 'rules' | 'budget';
  items: readonly string[];
}

/** Ids under `landing:brain.cards.<id>`; the copy lives in the locale files. */
export const BRAIN_CARDS: readonly BrainCard[] = [
  { id: 'memory', items: ['store', 'recall', 'lifecycle'] },
  { id: 'rules', items: ['yaml', 'hard', 'reload'] },
  { id: 'budget', items: ['assembled', 'folded', 'overBudget'] },
];
