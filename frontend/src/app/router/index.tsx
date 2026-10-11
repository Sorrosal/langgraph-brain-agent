import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';
import { env } from '@/shared/config/env';
import { useTheme } from '@/app/providers/ThemeProvider';
import { ThemeToggle } from '@/widgets/theme-toggle';
import { Skeleton } from '@/shared/ui/skeleton';
import { AuthGuard } from './guards/AuthGuard';
import { AppLayout } from './layouts/AppLayout';
import { AuthLayout } from './layouts/AuthLayout';
import { RootLayout } from './layouts/RootLayout';

function PageLoader() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

const LoginPage = lazy(() => import('@/pages/auth/LoginPage'));
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage'));
const ChatPage = lazy(() => import('@/pages/chat/ChatPage'));
const ApprovalsPage = lazy(() => import('@/pages/approvals/ApprovalsPage'));
const InspectorPage = lazy(() => import('@/pages/inspector/InspectorPage'));
const BrainPage = lazy(() => import('@/pages/brain/BrainPage'));
const DataPage = lazy(() => import('@/pages/data/DataPage'));
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage'));
const LandingPage = lazy(() => import('@/pages/landing/LandingPage'));
const NotFoundPage = lazy(() => import('@/pages/not-found/NotFoundPage'));

function page(element: React.ReactNode) {
  return <Suspense fallback={<PageLoader />}>{element}</Suspense>;
}

function LandingRoute() {
  const { theme, toggleTheme } = useTheme();
  return (
    <LandingPage
      showAppCta={!env.VITE_LANDING_ONLY}
      themeToggle={<ThemeToggle theme={theme} onToggle={toggleTheme} />}
    />
  );
}

const landingRoute: RouteObject = { path: '/', element: page(<LandingRoute />) };
const notFoundRoute: RouteObject = { path: '*', element: page(<NotFoundPage />) };

const appRoutes: RouteObject[] = [
  {
    element: <AuthLayout />,
    children: [
      { path: '/login', element: page(<LoginPage />) },
      { path: '/register', element: page(<RegisterPage />) },
    ],
  },

  // Protected routes with app layout
  {
    element: <AuthGuard />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/app', element: <Navigate to="/app/chat" replace /> },
          { path: '/app/chat', element: page(<ChatPage />) },
          { path: '/app/chat/:threadId', element: page(<ChatPage />) },
          { path: '/app/approvals', element: page(<ApprovalsPage />) },
          { path: '/app/inspector/:threadId?', element: page(<InspectorPage />) },
          { path: '/app/brain', element: page(<BrainPage />) },
          { path: '/app/data', element: page(<DataPage />) },
          { path: '/app/settings', element: page(<SettingsPage />) },
        ],
      },
    ],
  },
];

/** The landing is public; a landing-only build (GitHub Pages) ships no app routes at all. */
export function createRoutes(landingOnly: boolean): RouteObject[] {
  return [
    {
      element: <RootLayout />,
      children: [landingRoute, ...(landingOnly ? [] : appRoutes), notFoundRoute],
    },
  ];
}

export const router = createBrowserRouter(createRoutes(env.VITE_LANDING_ONLY), {
  basename: env.VITE_BASE_PATH,
});
