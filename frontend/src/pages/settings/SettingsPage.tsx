import { useAuthStore } from '@/features/auth';
import { env } from '@/shared/config/env';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card';

interface FieldProps {
  label: string;
  children: React.ReactNode;
}

function Field({ label, children }: FieldProps) {
  return (
    <div>
      <p className="text-muted-foreground text-sm font-medium">{label}</p>
      <div className="font-medium">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const user = useAuthStore((state) => state.user);

  return (
    <div className="flex max-w-2xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Your account and the backend this app talks to.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label="Name">{user?.display_name || '—'}</Field>
          <Field label="Email">{user?.email ?? '—'}</Field>
          <Field label="Role">
            <Badge variant="secondary">{user?.role ?? '—'}</Badge>
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Application</CardTitle>
          <CardDescription>Build-time configuration</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Field label="API URL">
            <span className="font-mono text-sm">{env.VITE_API_URL}</span>
          </Field>
          <Field label="App name">{env.VITE_APP_NAME}</Field>
        </CardContent>
      </Card>
    </div>
  );
}
