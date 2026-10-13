import { ChevronDown, LogOut, Menu, Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { useLogout, useAuthStore } from '@/features/auth';
import { LanguageSwitcher } from '@/features/switch-language';
import { NotificationCenter } from '@/features/notifications';
import { UserAvatar } from '@/entities/user';
import { Button } from '@/shared/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
import { Separator } from '@/shared/ui/separator';
import { findNavItem } from '@/widgets/sidebar';
import { ThemeToggle } from '@/widgets/theme-toggle';

interface HeaderProps {
  theme: 'light' | 'dark';
  onThemeToggle: () => void;
  /** Opens the navigation drawer (shown below `md`, where the sidebar is hidden). */
  onMenuClick: () => void;
}

export function Header({ theme, onThemeToggle, onMenuClick }: HeaderProps) {
  const { t } = useTranslation('shell');
  const { user } = useAuthStore();
  const logout = useLogout();
  const { pathname } = useLocation();
  const current = findNavItem(pathname);

  return (
    <header className="bg-background border-border flex h-14 shrink-0 items-center gap-2 border-b px-3 md:px-5">
      <Button
        variant="ghost"
        size="icon"
        className="-ml-1 shrink-0 max-md:size-11 md:hidden [&_svg]:size-5"
        aria-label={t('nav.open')}
        onClick={onMenuClick}
      >
        <Menu />
      </Button>

      <p className="font-display min-w-0 flex-1 truncate text-base font-semibold tracking-tight">
        {/* Other pages open with their own heading; repeating it here is noise. */}
        {current?.key === 'chat' ? t('nav.chat') : ''}
      </p>

      <div className="flex shrink-0 items-center md:gap-1">
        <LanguageSwitcher />
        <NotificationCenter />
        <ThemeToggle theme={theme} onToggle={onThemeToggle} />
        <Separator orientation="vertical" className="mx-1 h-6" />

        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="gap-2 px-1.5 max-md:h-11 sm:px-2"
                aria-label={t('user.menu')}
              >
                <UserAvatar user={user} size="sm" />
                <span className="hidden max-w-40 truncate text-sm font-medium sm:block">
                  {user.display_name}
                </span>
                <ChevronDown className="text-faint hidden sm:block" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[min(16rem,calc(100vw-2rem))]">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col gap-0.5">
                  <p className="truncate text-sm font-semibold">{user.display_name}</p>
                  <p className="text-muted-foreground truncate text-xs">{user.email}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild className="min-h-10 md:min-h-0">
                <Link to="/app/settings">
                  <Settings />
                  {t('user.settings')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-danger-fg focus:bg-danger-bg focus:text-danger-fg min-h-10 md:min-h-0"
                onClick={() => {
                  logout();
                }}
              >
                <LogOut />
                {t('user.signOut')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Button asChild size="sm">
            <Link to="/login">{t('user.signIn')}</Link>
          </Button>
        )}
      </div>
    </header>
  );
}
