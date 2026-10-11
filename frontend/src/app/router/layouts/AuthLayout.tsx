import { Zap } from 'lucide-react';
import { env } from '@/shared/config/env';
import { Outlet } from 'react-router-dom';

export function AuthLayout() {
  return (
    <div className="flex min-h-screen">
      {/* Left panel — branding */}
      <div className="bg-primary text-primary-foreground hidden flex-col justify-between p-10 lg:flex lg:w-1/2">
        <div className="flex items-center gap-2">
          <Zap className="h-7 w-7" />
          <span className="text-xl font-bold">{env.VITE_APP_NAME}</span>
        </div>
        <div>
          <p className="text-lg leading-relaxed">
            An agent that reasons, uses tools and asks for your approval before it acts.
          </p>
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
