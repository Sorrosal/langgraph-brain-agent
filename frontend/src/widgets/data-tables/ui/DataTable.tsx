import { Skeleton } from '@/shared/ui/skeleton';

export interface Column<T> {
  header: string;
  cell: (row: T) => React.ReactNode;
}

interface DataTableProps<T> {
  label: string;
  columns: readonly Column<T>[];
  rows: readonly T[] | undefined;
  rowKey: (row: T) => string;
  isLoading: boolean;
  isError: boolean;
}

/** Responsive table with loading, error and empty states. */
export function DataTable<T>({
  label,
  columns,
  rows,
  rowKey,
  isLoading,
  isError,
}: DataTableProps<T>) {
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError) return <p className="text-destructive text-sm">Could not load {label}.</p>;
  if (!rows?.length) return <p className="text-muted-foreground text-sm">No {label} found.</p>;

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-left text-sm" aria-label={label}>
        <thead className="bg-muted text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th key={column.header} className="px-3 py-2 font-medium whitespace-nowrap">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-t">
              {columns.map((column) => (
                <td key={column.header} className="px-3 py-2 align-top">
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
