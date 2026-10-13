import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';
import { env } from '@/shared/config/env';
import { useTheme } from '@/app/providers/ThemeProvider';
import { ThemeToggle } from '@/widgets/theme-toggle';
import { Skeleton } from '@/shared/ui/skeleton';
import { RouteError } from '@/shared/ui/route-error';
import { AuthGuard } from './guards/AuthGuard';
import { AppLayout } from './layouts/AppLayout';
import { AuthLayout } from './layouts/AuthLayout';
import { RootLayout } from './layouts/RootLayout';

/** Matches the page layout: title and subtitle, then two cards. */
function PageLoader() {
  const { t } = useTranslation();
  return (
    <div
      role="status"
      aria-busy="true"
      className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-4 sm:p-6 lg:p-8"
    >
      <span className="sr-only">{t('actions.loading')}</span>
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      <Skeleton className="h-40 w-full rounded-[var(--radius-lg)]" />
      <Skeleton className="h-40 w-full rounded-[var(--radius-lg)]" />
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
      errorElement: <RouteError />,
      children: [landingRoute, ...(landingOnly ? [] : appRoutes), notFoundRoute],
    },
  ];
}

export const router = createBrowserRouter(createRoutes(env.VITE_LANDING_ONLY), {
  basename: env.VITE_BASE_PATH,
});
