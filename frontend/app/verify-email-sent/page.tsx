'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Mail } from 'lucide-react';
import api from '@/lib/api';

export default function VerifyEmailSentPage() {
  const searchParams = useSearchParams();
  const email = searchParams.get('email') || '';
  const [isResending, setIsResending] = useState(false);
  const [resendMsg, setResendMsg] = useState('');

  const handleResend = async () => {
    if (!email) return;
    setIsResending(true);
    setResendMsg('');
    try {
      await api.post('/auth/resend-verification', { email });
      setResendMsg('Sent! Check your inbox (and spam folder).');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setResendMsg(
        typeof detail === 'string'
          ? detail
          : 'Please wait before requesting another email.',
      );
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-screen bg-void flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#161b22] border border-white/[0.08] rounded-2xl p-8 text-center shadow-2xl">
        <div className="w-16 h-16 rounded-full bg-gold/10 border border-gold/20 flex items-center justify-center mx-auto mb-6">
          <Mail className="w-8 h-8 text-gold" />
        </div>
        <h1 className="text-2xl font-bold text-ivory mb-2">Check your inbox</h1>
        <p className="text-sm text-muted mb-1">
          We&apos;ve sent a verification link to:
        </p>
        {email && (
          <p className="text-sm font-semibold text-gold mb-6 break-all">{email}</p>
        )}
        <p className="text-xs text-muted mb-8">
          Click the link in the email to verify your account before logging in.
          The link expires in 24 hours.
        </p>

        {resendMsg && (
          <p className="text-xs text-fern mb-4">{resendMsg}</p>
        )}

        <button
          onClick={handleResend}
          disabled={isResending || !email}
          className="w-full mb-4 py-2.5 rounded-xl border border-white/[0.12] text-fern text-sm font-medium hover:border-gold/40 hover:text-ivory transition-colors disabled:opacity-40"
        >
          {isResending ? 'Sending…' : 'Resend verification email'}
        </button>

        <Link
          href="/login"
          className="block text-xs text-muted hover:text-ivory transition-colors"
        >
          Back to login
        </Link>
      </div>
    </div>
  );
}
