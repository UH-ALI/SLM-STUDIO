'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Mail, KeyRound, Eye, EyeOff } from 'lucide-react';
import { Button } from '@/components/atoms/Button';
import { PasswordRequirements, allPasswordRequirementsMet } from '@/components/molecules/PasswordRequirements';
import { AuthLayout } from '@/components/templates/AuthLayout';
import { useUIStore } from '@/stores/uiStore';
import api from '@/lib/api';

// [FEATURE] Real forgot-password flow, replacing the earlier placeholder
// page. Two steps against the new backend endpoints:
//   1. POST /auth/forgot-password  { email }        -> emails a 6-digit code
//   2. POST /auth/reset-password   { email, code, newPassword }
//
// Step 1 always shows the same generic confirmation regardless of whether
// the email is actually registered (see the backend endpoint's own comment
// for why — this is the one place in the auth flow where we deliberately
// don't reveal that).
export default function ForgotPasswordPage() {
  const router = useRouter();
  const { addToast } = useUIStore();

  const [step, setStep] = useState<'request' | 'reset'>('request');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleRequestCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError('Enter your email address.');
      return;
    }
    setError('');
    setIsLoading(true);
    try {
      await api.post('/auth/forgot-password', { email });
      addToast({ type: 'success', message: 'If that email exists, a code is on its way.' });
      setStep('reset');
    } catch (err: any) {
      // This request essentially can't fail in a way the user needs to see
      // (the backend always returns 200 with a generic message), so this
      // branch only fires on genuine network/CORS failures.
      setError(err?.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) {
      setError('Enter the code from your email.');
      return;
    }
    if (!allPasswordRequirementsMet(newPassword)) {
      setError('Password does not meet the requirements below.');
      return;
    }
    setError('');
    setIsLoading(true);
    try {
      await api.post('/auth/reset-password', { email, code: code.trim(), newPassword });
      addToast({ type: 'success', message: 'Password reset. Please sign in.' });
      router.push('/login');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'That code is invalid or has expired.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout variant="login">
      {step === 'request' ? (
        <form onSubmit={handleRequestCode} className="space-y-4">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-void mb-1">Reset your password</h2>
            <p className="text-sm text-muted">
              Enter your account email and we&apos;ll send you a reset code.
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose/10 border border-rose/20 text-sm text-rose text-center">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-void/80 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-white/60 border border-void/10 rounded-button px-3.5 py-2.5 text-sm text-void placeholder:text-muted focus:outline-none focus:border-gold/50 transition-colors"
            />
          </div>

          <Button type="submit" fullWidth isLoading={isLoading} icon={Mail}>
            Send reset code
          </Button>

          <p className="text-center text-xs text-muted mt-4">
            <Link href="/login" className="text-gold hover:underline font-medium">
              Back to sign in
            </Link>
          </p>
        </form>
      ) : (
        <form onSubmit={handleResetPassword} className="space-y-4">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-void mb-1">Enter your code</h2>
            <p className="text-sm text-muted">
              Check <span className="text-void/80 font-medium">{email}</span> for a 6-digit code.
              It expires in 15 minutes.
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose/10 border border-rose/20 text-sm text-rose text-center">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-void/80 mb-1.5">Reset code</label>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              className="w-full bg-white/60 border border-void/10 rounded-button px-3.5 py-2.5 text-sm text-void placeholder:text-muted tracking-[0.3em] text-center focus:outline-none focus:border-gold/50 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-void/80 mb-1.5">New password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Min 8 characters"
                className="w-full bg-white/60 border border-void/10 rounded-button px-3.5 py-2.5 pr-10 text-sm text-void placeholder:text-muted focus:outline-none focus:border-gold/50 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-void transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <PasswordRequirements password={newPassword} />
          </div>

          <Button type="submit" fullWidth isLoading={isLoading} icon={KeyRound}>
            Reset password
          </Button>

          <p className="text-center text-xs text-muted mt-4">
            Didn&apos;t get a code?{' '}
            <button
              type="button"
              onClick={() => setStep('request')}
              className="text-gold hover:underline font-medium"
            >
              Try again
            </button>
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
