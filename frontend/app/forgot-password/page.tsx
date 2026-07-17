'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Send } from 'lucide-react';
import api from '@/lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }

    setIsLoading(true);
    setError('');
    try {
      await api.post('/auth/forgot-password', { email });
      setSubmitted(true);
    } catch {
      // Even on error, show the generic message (anti-enumeration)
      setSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-void flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#161b22] border border-white/[0.08] rounded-2xl p-8 shadow-2xl">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-2xl font-bold text-gold mb-1">
            SLM <span className="text-fern">Studio</span>
          </div>
          <h1 className="text-xl font-semibold text-ivory mt-4 mb-1">Forgot your password?</h1>
          <p className="text-sm text-muted">
            Enter your email and we&apos;ll send you a reset link.
          </p>
        </div>

        {submitted ? (
          <div className="text-center">
            <div className="w-14 h-14 rounded-full bg-fern/10 border border-fern/20 flex items-center justify-center mx-auto mb-4">
              <Send className="w-6 h-6 text-fern" />
            </div>
            <p className="text-sm text-ivory font-medium mb-2">Check your inbox</p>
            <p className="text-sm text-muted mb-6">
              If an account exists with that email, a reset link has been sent.
              The link expires in 15 minutes.
            </p>
            <Link
              href="/login"
              className="text-sm text-gold hover:underline"
            >
              Back to login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-ivory/80 mb-1.5">
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full bg-white/[0.04] border border-white/[0.10] rounded-xl px-3.5 py-2.5 text-sm text-ivory placeholder:text-muted focus:outline-none focus:border-gold/50 transition-colors"
              />
              {error && <p className="mt-1 text-xs text-rose">{error}</p>}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-xl bg-gold text-void font-semibold text-sm hover:bg-amber transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isLoading ? 'Sending…' : (
                <><Send className="w-4 h-4" /> Send reset link</>
              )}
            </button>

            <p className="text-center text-xs text-muted">
              Remember your password?{' '}
              <Link href="/login" className="text-gold hover:underline">
                Sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
