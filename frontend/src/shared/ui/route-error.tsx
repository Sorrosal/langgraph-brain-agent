import { RotateCw } from 'lucide-react';
import { useRouteError } from 'react-router-dom';
import { Button } from '@/shared/ui/button';

/** Router `errorElement`: a failed lazy chunk or render error shows a retry, not a blank screen. */
export function RouteError() {
  const error = useRouteError();
  const detail = error instanceof Error ? error.message : null;
  return (
    <div
      role="alert"
      className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center"
    >
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <p className="text-muted-foreground max-w-sm">
        The page could not be loaded. Check your connection and try again.
      </p>
      {detail && <p className="text-muted-foreground max-w-sm font-mono text-xs">{detail}</p>}
      <Button
        onClick={() => {
          window.location.reload();
        }}
      >
        <RotateCw className="mr-2 h-4 w-4" />
        Retry
      </Button>
    </div>
  );
}
