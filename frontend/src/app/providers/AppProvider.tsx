import { Toaster } from '@/shared/ui/sonner';
import { QueryProvider } from './QueryProvider';
import { RouterProvider } from './RouterProvider';
import { ThemeProvider } from './ThemeProvider';

export function AppProvider() {
  return (
    <QueryProvider>
      <ThemeProvider>
        <RouterProvider />
        <Toaster richColors position="top-right" />
      </ThemeProvider>
    </QueryProvider>
  );
}
