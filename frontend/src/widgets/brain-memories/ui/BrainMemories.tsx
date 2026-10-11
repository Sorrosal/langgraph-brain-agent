import { useState } from 'react';
import { MemoryCard, useMemories, useMemorySearch, memoryKindSchema } from '@/entities/memory';
import type { MemoryKind } from '@/entities/memory';
import { AddMemoryForm, DeleteMemoryButton } from '@/features/manage-memory';
import { useDebounce } from '@/shared/hooks/use-debounce';
import { Input } from '@/shared/ui/input';
import { Skeleton } from '@/shared/ui/skeleton';

const SEARCH_DELAY_MS = 300;

export function BrainMemories() {
  const [kind, setKind] = useState<MemoryKind | null>(null);
  const [search, setSearch] = useState('');
  const query = useDebounce(search.trim(), SEARCH_DELAY_MS);
  const searching = query.length > 0;

  const listed = useMemories(kind);
  const found = useMemorySearch(query);
  const { data, isLoading, isError } = searching ? found : listed;
  // search is semantic across kinds, so the kind filter narrows its results client-side
  const memories = searching && kind ? data?.filter((m) => m.kind === kind) : data;

  return (
    <div className="flex flex-col gap-4">
      <AddMemoryForm />
      <div className="flex flex-col gap-2 sm:flex-row">
        <select
          aria-label="Filter by kind"
          className="border-input bg-background h-9 rounded-md border px-2 text-sm"
          value={kind ?? ''}
          onChange={(e) => {
            setKind(e.target.value ? memoryKindSchema.parse(e.target.value) : null);
          }}
        >
          <option value="">All kinds</option>
          {memoryKindSchema.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <Input
          type="search"
          aria-label="Search memories"
          placeholder="Search memories by meaning…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
          }}
        />
      </div>
      {isLoading && <Skeleton className="h-20 w-full" />}
      {isError && <p className="text-destructive text-sm">Could not load memories.</p>}
      {memories?.length === 0 && (
        <p className="text-muted-foreground text-sm">
          {searching ? 'No memories match your search.' : 'No memories yet.'}
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {memories?.map((memory) => (
          <li key={memory.id}>
            <MemoryCard memory={memory} actions={<DeleteMemoryButton memoryId={memory.id} />} />
          </li>
        ))}
      </ul>
    </div>
  );
}
