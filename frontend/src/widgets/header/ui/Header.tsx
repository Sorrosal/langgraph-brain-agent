import { LogOut, Settings } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useLogout, useAuthStore } from '@/features/auth';
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
import { ThemeToggle } from '@/widgets/theme-toggle';

interface HeaderProps {
  theme: 'light' | 'dark';
  onThemeToggle: () => void;
}

export function Header({ theme, onThemeToggle }: HeaderProps) {
  const { user } = useAuthStore();
  const { mutate: logout } = useLogout();
  const navigate = useNavigate();

  return (
    <header className="bg-card border-border flex h-14 items-center gap-4 border-b px-4">
      <div className="flex-1" />

      <div className="flex items-center gap-2">
        <NotificationCenter />
        <ThemeToggle theme={theme} onToggle={onThemeToggle} />
        <Separator orientation="vertical" className="h-6" />

        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="flex items-center gap-2 px-2"
                aria-label="User menu"
              >
                <UserAvatar user={user} size="sm" />
                <span className="hidden text-sm font-medium sm:block">{user.name}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col gap-0.5">
                  <p className="text-sm font-semibold">{user.name}</p>
                  <p className="text-muted-foreground text-xs">{user.email}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => void navigate('/settings')}>
                <Settings className="mr-2 h-4 w-4" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => {
                  logout();
                }}
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Button asChild size="sm">
            <Link to="/login">Sign in</Link>
          </Button>
        )}
      </div>
    </header>
  );
}
