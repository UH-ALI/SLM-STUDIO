import type { Metadata } from 'next';
import { AuthLayout } from '@/components/templates/AuthLayout';
import { SignupForm } from '@/components/forms/SignupForm';

export const metadata: Metadata = {
  title: 'Create Account',
  description: 'Create your SLM Studio account',
  robots: {
    index: false,
    follow: false,
  },
};

export default function SignupPage() {
  return (
    <AuthLayout variant="signup">
      <SignupForm />
    </AuthLayout>
  );
}
