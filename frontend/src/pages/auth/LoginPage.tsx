import { Link } from 'react-router-dom';
import { LoginForm } from '@/features/auth';

export default function LoginPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2 text-center">
        <h1 className="text-2xl font-bold">Welcome back</h1>
        <p className="text-muted-foreground text-sm">
          Enter your credentials to access your account
        </p>
      </div>

      <LoginForm />

      <p className="text-muted-foreground text-center text-sm">
        Don&apos;t have an account?{' '}
        <Link to="/register" className="text-foreground font-medium underline underline-offset-4">
          Sign up
        </Link>
      </p>
    </div>
  );
}
