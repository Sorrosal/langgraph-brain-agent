import { ChevronLeft, ChevronRight, LogOut, MessageSquare, Settings, Zap } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useLogout } from '@/features/auth';
import { env } from '@/shared/config/env';
import { Button } from '@/shared/ui/button';
import { Separator } from '@/shared/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/ui/tooltip';
import { cn } from '@/shared/lib/cn';
import { useMediaQuery } from '@/shared/hooks/use-media-query';
import { useSidebarStore } from '../model/sidebar.store';

interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

const navItems: NavItem[] = [
  { to: '/app/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/app/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar() {
  const { isCollapsed, toggle } = useSidebarStore();
  const isMobile = useMediaQuery('(max-width: 768px)');
  const logout = useLogout();

  if (isMobile) return null;

  return (
    <aside
      className={cn(
        'bg-card border-border flex h-full flex-col border-r transition-all duration-200',
        isCollapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center px-4">
        <div className="flex items-center gap-2">
          <Zap className="text-primary h-6 w-6 shrink-0" />
          {!isCollapsed && <span className="truncate font-bold">{env.VITE_APP_NAME}</span>}
        </div>
      </div>

      <Separator />

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2">
        <TooltipProvider delayDuration={0}>
          <ul className="flex flex-col gap-1 px-2">
            {navItems.map((item) => (
              <li key={item.to}>
                {isCollapsed ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <NavLink
                        to={item.to}
                        className={({ isActive }) =>
                          cn(
                            'flex h-9 w-9 items-center justify-center rounded-md transition-colors',
                            isActive
                              ? 'bg-primary text-primary-foreground'
                              : 'hover:bg-accent hover:text-accent-foreground',
                          )
                        }
                        aria-label={item.label}
                      >
                        <item.icon className="h-5 w-5" />
                      </NavLink>
                    </TooltipTrigger>
                    <TooltipContent side="right">{item.label}</TooltipContent>
                  </Tooltip>
                ) : (
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        'flex h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors',
                        isActive
                          ? 'bg-primary text-primary-foreground font-medium'
                          : 'hover:bg-accent hover:text-accent-foreground',
                      )
                    }
                  >
                    <item.icon className="h-5 w-5 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </NavLink>
                )}
              </li>
            ))}
          </ul>
        </TooltipProvider>
      </nav>

      <Separator />

      {/* Footer */}
      <div className="flex flex-col gap-1 p-2">
        {isCollapsed ? (
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9"
                  aria-label="Sign out"
                  onClick={() => {
                    logout();
                  }}
                >
                  <LogOut className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Sign out</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : (
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 px-3"
            onClick={() => {
              logout();
            }}
          >
            <LogOut className="h-5 w-5 shrink-0" />
            <span>Sign out</span>
          </Button>
        )}

        <Button
          variant="ghost"
          size="icon"
          className="ml-auto h-9 w-9"
          onClick={toggle}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>
    </aside>
  );
}
