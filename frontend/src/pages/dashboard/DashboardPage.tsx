import { Activity, DollarSign, TrendingUp, Users } from 'lucide-react';
import { Badge } from '@/shared/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card';
import { useAuthStore } from '@/features/auth';

const stats = [
  {
    title: 'Total Revenue',
    value: '$45,231.89',
    change: '+20.1%',
    icon: DollarSign,
    trend: 'up' as const,
  },
  {
    title: 'Active Users',
    value: '2,350',
    change: '+180 this month',
    icon: Users,
    trend: 'up' as const,
  },
  {
    title: 'New Orders',
    value: '1,247',
    change: '+19% from last month',
    icon: Activity,
    trend: 'up' as const,
  },
  {
    title: 'Growth Rate',
    value: '+12.5%',
    change: 'Compared to last quarter',
    icon: TrendingUp,
    trend: 'up' as const,
  },
];

const recentActivity = [
  { id: '1', user: 'Alice Johnson', action: 'Created a new project', time: '2 minutes ago' },
  { id: '2', user: 'Bob Smith', action: 'Completed task #1234', time: '15 minutes ago' },
  { id: '3', user: 'Carol White', action: 'Updated settings', time: '1 hour ago' },
  { id: '4', user: 'David Brown', action: 'Joined the team', time: '3 hours ago' },
  { id: '5', user: 'Eve Davis', action: 'Submitted a report', time: 'Yesterday' },
];

export default function DashboardPage() {
  const { user } = useAuthStore();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Welcome back{user ? `, ${user.name.split(' ')[0] ?? user.name}` : ''}!
        </h1>
        <p className="text-muted-foreground">Here&apos;s what&apos;s happening today.</p>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
              <stat.icon className="text-muted-foreground h-4 w-4" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-muted-foreground mt-1 text-xs">{stat.change}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Latest actions from your team members</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3">
            {recentActivity.map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{item.user}</p>
                  <p className="text-muted-foreground truncate text-xs">{item.action}</p>
                </div>
                <Badge variant="secondary" className="shrink-0 text-xs">
                  {item.time}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
