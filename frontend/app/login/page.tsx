import type { Metadata } from 'next';
import { AuthLayout } from '@/components/templates/AuthLayout';
import { LoginForm } from '@/components/forms/LoginForm';

export const metadata: Metadata = {
  title: 'Sign In',
  description: 'Sign in to your SLM Studio account',
  robots: {
    index: false,
    follow: false,
  },
};

export default function LoginPage() {
  return (
    <AuthLayout variant="login">
      <LoginForm />
    </AuthLayout>
  );
}
