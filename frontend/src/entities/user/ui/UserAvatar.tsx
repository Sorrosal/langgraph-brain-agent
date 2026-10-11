import { Avatar, AvatarFallback } from '@/shared/ui/avatar';
import { cn } from '@/shared/lib/cn';
import type { User } from '../model/user.types';

interface UserAvatarProps {
  user: Pick<User, 'display_name' | 'email'>;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-14 w-14 text-base',
} as const;

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((part) => part[0] ?? '')
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export function UserAvatar({ user, size = 'md', className }: UserAvatarProps) {
  const name = user.display_name || user.email;
  return (
    <Avatar className={cn(sizeClasses[size], className)}>
      <AvatarFallback>{getInitials(name)}</AvatarFallback>
    </Avatar>
  );
}
