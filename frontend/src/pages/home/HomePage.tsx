import { ArrowRight, Shield, Zap, Code2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/shared/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card';

const features = [
  {
    icon: Zap,
    title: 'Feature-Sliced Design',
    description: 'Scalable architecture with strict layer boundaries and clear slice structure.',
  },
  {
    icon: Shield,
    title: 'Type-Safe & Strict',
    description: 'Full TypeScript strict mode with zero any and runtime Zod validation.',
  },
  {
    icon: Code2,
    title: 'Modern Stack',
    description: 'React 19, Vite, TanStack Query v5, Zustand, shadcn/ui, and Tailwind v4.',
  },
];

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center border-b px-6">
        <div className="flex items-center gap-2">
          <Zap className="h-6 w-6" />
          <span className="font-bold">React Spark</span>
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="ghost" asChild>
            <Link to="/login">Sign in</Link>
          </Button>
          <Button asChild>
            <Link to="/register">Get started</Link>
          </Button>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="flex flex-col items-center justify-center gap-6 px-4 py-24 text-center">
          <h1 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
            Build React SPAs the <span className="text-primary">right way</span>
          </h1>
          <p className="text-muted-foreground max-w-xl text-lg">
            A production-ready template with Feature-Sliced Design, strict TypeScript, and all the
            tools you need to ship fast.
          </p>
          <div className="flex gap-3">
            <Button size="lg" asChild>
              <Link to="/dashboard">
                View Dashboard <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link to="/register">Get started free</Link>
            </Button>
          </div>
        </section>

        {/* Features */}
        <section className="mx-auto max-w-5xl px-4 pb-24">
          <div className="grid gap-6 sm:grid-cols-3">
            {features.map((feature) => (
              <Card key={feature.title}>
                <CardHeader>
                  <feature.icon className="mb-2 h-8 w-8" />
                  <CardTitle>{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription>{feature.description}</CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
