import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet } from 'react-router-dom';
import { useTheme } from '@/app/providers/ThemeProvider';
import { useApprovalNotifications } from '@/features/notifications';
import { useMediaQuery } from '@/shared/hooks/use-media-query';
import { Header } from '@/widgets/header';
import { MobileSidebar, Sidebar } from '@/widgets/sidebar';

/** Prism shell: glass sidebar and a rounded content sheet floating on the page backdrop. */
export function AppLayout() {
  const { t } = useTranslation('shell');
  const { theme, toggleTheme } = useTheme();
  const [navOpen, setNavOpen] = useState(false);
  const isDesktop = useMediaQuery('(min-width: 768px)');
  useApprovalNotifications();

  return (
    <div className="flex h-dvh overflow-hidden md:gap-3 md:p-3">
      <a
        href="#main-content"
        className="bg-elevated text-foreground shadow-e3 sr-only z-[60] rounded-[var(--radius-md)] px-4 py-2 text-sm font-medium focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        {t('skipToContent')}
      </a>
      <Sidebar />
      <MobileSidebar open={navOpen && !isDesktop} onOpenChange={setNavOpen} />
      <div className="bg-background md:shadow-e1 flex min-w-0 flex-1 flex-col overflow-hidden md:rounded-[var(--radius-xl)]">
        <Header
          theme={theme}
          onThemeToggle={toggleTheme}
          onMenuClick={() => {
            setNavOpen(true);
          }}
        />
        <main
          id="main-content"
          tabIndex={-1}
          className="min-h-0 flex-1 overflow-y-auto focus:outline-none"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
