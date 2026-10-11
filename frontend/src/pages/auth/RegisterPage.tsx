import { Link } from 'react-router-dom';
import { RegisterForm } from '@/features/auth';

export default function RegisterPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2 text-center">
        <h1 className="text-2xl font-bold">Create an account</h1>
        <p className="text-muted-foreground text-sm">Enter your details to get started for free</p>
      </div>

      <RegisterForm />

      <p className="text-muted-foreground text-center text-sm">
        Already have an account?{' '}
        <Link to="/login" className="text-foreground font-medium underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </div>
  );
}
