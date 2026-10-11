import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
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
const NotFoundPage = lazy(() => import('@/pages/not-found/NotFoundPage'));

function page(element: React.ReactNode) {
  return <Suspense fallback={<PageLoader />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          { path: '/login', element: page(<LoginPage />) },
          { path: '/register', element: page(<RegisterPage />) },
        ],
      },

      { path: '/', element: <Navigate to="/app/chat" replace /> },

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

      { path: '*', element: page(<NotFoundPage />) },
    ],
  },
]);
