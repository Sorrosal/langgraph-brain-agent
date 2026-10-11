import { Zap } from 'lucide-react';
import { Outlet } from 'react-router-dom';

export function AuthLayout() {
  return (
    <div className="flex min-h-screen">
      {/* Left panel — branding */}
      <div className="bg-primary text-primary-foreground hidden flex-col justify-between p-10 lg:flex lg:w-1/2">
        <div className="flex items-center gap-2">
          <Zap className="h-7 w-7" />
          <span className="text-xl font-bold">React Spark</span>
        </div>
        <div>
          <blockquote className="space-y-2">
            <p className="text-lg leading-relaxed">
              &ldquo;A professional template built with Feature-Sliced Design, React 19, and the
              best tools in the ecosystem.&rdquo;
            </p>
            <footer className="text-sm opacity-80">— React Spark Template</footer>
          </blockquote>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
