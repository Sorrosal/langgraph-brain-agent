import { ChevronsLeft, ChevronsRight, LogOut, type LucideIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';
import { useLogout } from '@/features/auth';
import { usePendingApprovals } from '@/entities/pending-approval';
import { env } from '@/shared/config/env';
import { cn } from '@/shared/lib/cn';
import { Sheet, SheetContent, SheetTitle } from '@/shared/ui/sheet';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/ui/tooltip';
import { navItems } from '../model/nav-items';
import { useSidebarStore } from '../model/sidebar.store';

const MAX_BADGE = 99;

function rowClass(collapsed: boolean) {
  return cn(
    'flex h-11 w-full items-center gap-3 rounded-[var(--radius-md)] px-3 text-sm transition-colors md:h-10',
    collapsed && 'justify-center px-0',
  );
}

/** In collapsed mode the label only lives in a tooltip (and as sr-only text on the control). */
function WithTooltip({
  label,
  enabled,
  children,
}: {
  label: string;
  enabled: boolean;
  children: React.ReactElement;
}) {
  if (!enabled) return children;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

function CountBadge({ count, collapsed }: { count: number; collapsed: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'bg-primary text-primary-foreground text-2xs flex items-center justify-center rounded-full font-semibold tabular-nums',
        collapsed ? 'absolute top-1 right-1.5 h-4 min-w-4 px-1' : 'ml-auto h-5 min-w-5 px-1.5',
      )}
    >
      {count > MAX_BADGE ? `${String(MAX_BADGE)}+` : count}
    </span>
  );
}

interface ActionRowProps {
  icon: LucideIcon;
  label: string;
  collapsed: boolean;
  onClick: () => void;
}

function ActionRow({ icon: Icon, label, collapsed, onClick }: ActionRowProps) {
  return (
    <WithTooltip label={label} enabled={collapsed}>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          rowClass(collapsed),
          'text-muted-foreground hover:bg-muted hover:text-foreground',
        )}
      >
        <Icon className="size-[1.125rem] shrink-0" aria-hidden="true" />
        <span className={collapsed ? 'sr-only' : 'truncate'}>{label}</span>
      </button>
    </WithTooltip>
  );
}

interface SidebarPanelProps {
  collapsed: boolean;
  onNavigate?: () => void;
  /** Desktop only: the collapse/expand control. */
  onToggle?: () => void;
}

/** Brand, navigation and account actions; shared by the desktop rail and the mobile drawer. */
function SidebarPanel({ collapsed, onNavigate, onToggle }: SidebarPanelProps) {
  const { t } = useTranslation('shell');
  const logout = useLogout();
  const { data: pending } = usePendingApprovals();
  const pendingCount = pending?.length ?? 0;

  return (
    <TooltipProvider delayDuration={0}>
      <div
        className={cn(
          'flex h-14 shrink-0 items-center gap-2.5 px-4',
          collapsed && 'justify-center px-0',
        )}
      >
        <span className="ev-orb size-7 shrink-0" aria-hidden="true" />
        {!collapsed && (
          <span className="font-display truncate text-base font-semibold tracking-tight">
            {env.VITE_APP_NAME}
          </span>
        )}
      </div>

      <nav aria-label={t('nav.label')} className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        <ul className="flex flex-col gap-1">
          {navItems.map((item) => {
            const label = t(`nav.${item.key}`);
            const count = item.key === 'approvals' ? pendingCount : 0;
            return (
              <li key={item.to}>
                <WithTooltip
                  label={count > 0 ? `${label} · ${t('nav.pending', { count })}` : label}
                  enabled={collapsed}
                >
                  <NavLink
                    to={item.to}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        rowClass(collapsed),
                        'relative',
                        isActive
                          ? 'bg-accent text-accent-foreground font-medium'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )
                    }
                  >
                    <item.icon className="size-[1.125rem] shrink-0" aria-hidden="true" />
                    <span className={collapsed ? 'sr-only' : 'truncate'}>{label}</span>
                    {count > 0 && (
                      <>
                        <CountBadge count={count} collapsed={collapsed} />
                        <span className="sr-only">{t('nav.pending', { count })}</span>
                      </>
                    )}
                  </NavLink>
                </WithTooltip>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-border flex shrink-0 flex-col gap-1 border-t p-2">
        <ActionRow
          icon={LogOut}
          label={t('nav.signOut')}
          collapsed={collapsed}
          onClick={() => {
            logout();
          }}
        />
        {onToggle && (
          <ActionRow
            icon={collapsed ? ChevronsRight : ChevronsLeft}
            label={collapsed ? t('nav.expand') : t('nav.collapse')}
            collapsed={collapsed}
            onClick={onToggle}
          />
        )}
      </div>
    </TooltipProvider>
  );
}

/** Desktop rail (hidden below `md`; the header's menu button opens `MobileSidebar` instead). */
export function Sidebar() {
  const { isCollapsed, toggle } = useSidebarStore();

  return (
    <aside
      className={cn(
        'glass hidden shrink-0 flex-col overflow-hidden rounded-[var(--radius-xl)] transition-[width] duration-200 md:flex',
        isCollapsed ? 'w-[var(--sidebar-width-collapsed)]' : 'w-[var(--sidebar-width)]',
      )}
    >
      <SidebarPanel collapsed={isCollapsed} onToggle={toggle} />
    </aside>
  );
}

interface MobileSidebarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MobileSidebar({ open, onOpenChange }: MobileSidebarProps) {
  const { t } = useTranslation('shell');

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        aria-describedby={undefined}
        className="flex w-[min(18rem,85vw)] flex-col gap-0 p-0 sm:max-w-none"
      >
        <SheetTitle className="sr-only">{t('nav.title')}</SheetTitle>
        <SidebarPanel
          collapsed={false}
          onNavigate={() => {
            onOpenChange(false);
          }}
        />
      </SheetContent>
    </Sheet>
  );
}
