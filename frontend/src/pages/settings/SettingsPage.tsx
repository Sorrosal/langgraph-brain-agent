import { useAuthStore } from '@/features/auth';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card';
import { Separator } from '@/shared/ui/separator';
import { Badge } from '@/shared/ui/badge';

export default function SettingsPage() {
  const { user } = useAuthStore();

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Manage your account and application preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-muted-foreground text-sm font-medium">Name</p>
              <p className="font-medium">{user?.name ?? '—'}</p>
            </div>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-muted-foreground text-sm font-medium">Email</p>
              <p className="font-medium">{user?.email ?? '—'}</p>
            </div>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-muted-foreground text-sm font-medium">Role</p>
              <Badge variant="secondary" className="mt-1">
                {user?.role ?? '—'}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Application</CardTitle>
          <CardDescription>Template configuration and environment</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <p className="text-muted-foreground text-sm font-medium">API URL</p>
            <p className="font-mono text-sm">
              {(import.meta.env['VITE_API_URL'] as string | undefined) ?? 'Not configured'}
            </p>
          </div>
          <Separator />
          <div>
            <p className="text-muted-foreground text-sm font-medium">App Name</p>
            <p className="font-medium">
              {(import.meta.env['VITE_APP_NAME'] as string | undefined) ?? 'React Spark'}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
