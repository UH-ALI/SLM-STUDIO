'use client';

import { useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, KeyRound } from 'lucide-react';
import api from '@/lib/api';

export default function ResetPasswordPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState(false);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (password.length < 8) errs.password = 'Password must be at least 8 characters';
    else if (!/[A-Z]/.test(password)) errs.password = 'Password must contain at least one uppercase letter';
    else if (!/\d/.test(password)) errs.password = 'Password must contain at least one digit';
    if (confirm !== password) errs.confirm = 'Passwords do not match';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsLoading(true);
    setErrors({});
    try {
      await api.post('/auth/reset-password', { token, new_password: password });
      setSuccess(true);
      setTimeout(() => router.push('/login'), 3000);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setErrors({
        general: typeof detail === 'string'
          ? detail
          : 'This reset link has expired or has already been used. Please request a new one.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-[#161b22] border border-white/[0.08] rounded-2xl p-8 text-center">
          <p className="text-sm text-muted mb-4">Invalid or missing reset token.</p>
          <Link href="/forgot-password" className="text-sm text-gold hover:underline">
            Request a new reset link
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-void flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#161b22] border border-white/[0.08] rounded-2xl p-8 shadow-2xl">
        <div className="text-center mb-8">
          <div className="text-2xl font-bold text-gold mb-1">
            SLM <span className="text-fern">Studio</span>
          </div>
          <h1 className="text-xl font-semibold text-ivory mt-4 mb-1">Reset your password</h1>
          <p className="text-sm text-muted">Choose a strong new password.</p>
        </div>

        {success ? (
          <div className="text-center">
            <KeyRound className="w-10 h-10 text-fern mx-auto mb-4" />
            <p className="text-sm text-ivory font-medium mb-2">Password updated!</p>
            <p className="text-sm text-muted">Redirecting you to login…</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {errors.general && (
              <div className="p-3 rounded-xl bg-rose/10 border border-rose/20 text-sm text-rose text-center">
                {errors.general}
                <Link href="/forgot-password" className="block mt-1 text-xs underline">
                  Request a new reset link
                </Link>
              </div>
            )}

            {/* New password */}
            <div>
              <label className="block text-xs font-semibold text-ivory/80 mb-1.5">
                New password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 8 chars, 1 uppercase, 1 digit"
                  className="w-full bg-white/[0.04] border border-white/[0.10] rounded-xl px-3.5 py-2.5 pr-10 text-sm text-ivory placeholder:text-muted focus:outline-none focus:border-gold/50 transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-ivory"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && <p className="mt-1 text-xs text-rose">{errors.password}</p>}
            </div>

            {/* Confirm */}
            <div>
              <label className="block text-xs font-semibold text-ivory/80 mb-1.5">
                Confirm new password
              </label>
              <input
                type={showPassword ? 'text' : 'password'}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter your new password"
                className="w-full bg-white/[0.04] border border-white/[0.10] rounded-xl px-3.5 py-2.5 text-sm text-ivory placeholder:text-muted focus:outline-none focus:border-gold/50 transition-colors"
              />
              {errors.confirm && <p className="mt-1 text-xs text-rose">{errors.confirm}</p>}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-xl bg-gold text-void font-semibold text-sm hover:bg-amber transition-colors disabled:opacity-50"
            >
              {isLoading ? 'Updating…' : 'Set new password'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
