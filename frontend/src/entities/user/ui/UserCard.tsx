import { Badge } from '@/shared/ui/badge';
import { Card, CardContent } from '@/shared/ui/card';
import { cn } from '@/shared/lib/cn';
import type { User } from '../model/user.types';
import { UserAvatar } from './UserAvatar';

interface UserCardProps {
  user: User;
  className?: string;
}

const roleBadgeVariants = {
  admin: 'destructive',
  editor: 'default',
  viewer: 'secondary',
} as const;

export function UserCard({ user, className }: UserCardProps) {
  return (
    <Card className={cn('w-full', className)}>
      <CardContent className="flex items-center gap-4 p-4">
        <UserAvatar user={user} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{user.name}</p>
          <p className="text-muted-foreground truncate text-sm">{user.email}</p>
        </div>
        <Badge variant={roleBadgeVariants[user.role]}>{user.role}</Badge>
      </CardContent>
    </Card>
  );
}
