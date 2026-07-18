'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import api from '@/lib/api';

type Status = 'loading' | 'success' | 'error';

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<Status>('loading');
  const [message, setMessage] = useState('');
  const [isResending, setIsResending] = useState(false);

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('No verification token found. Please check your email link.');
      return;
    }

    api.get(`/auth/verify-email?token=${token}`)
      .then((res) => {
        setStatus('success');
        setMessage(res.data.message || 'Email verified successfully!');
        setTimeout(() => router.push('/login'), 3000);
      })
      .catch((err) => {
        setStatus('error');
        const detail = err?.response?.data?.detail;
        setMessage(
          typeof detail === 'string'
            ? detail
            : 'This verification link has expired or is invalid. Please request a new one.',
        );
      });
  }, [token, router]);

  const handleResend = async () => {
    const email = searchParams.get('email');
    if (!email) return;
    setIsResending(true);
    try {
      await api.post('/auth/resend-verification', { email });
      setMessage('A new verification email has been sent. Please check your inbox.');
    } catch {
      setMessage('Could not resend email. Please wait a moment and try again.');
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-screen bg-void flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#161b22] border border-white/[0.08] rounded-2xl p-8 text-center shadow-2xl">
        {status === 'loading' && (
          <>
            <Loader2 className="w-12 h-12 text-gold mx-auto mb-4 animate-spin" />
            <h1 className="text-xl font-semibold text-ivory mb-2">Verifying your email…</h1>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircle className="w-12 h-12 text-fern mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-ivory mb-2">Email verified!</h1>
            <p className="text-sm text-muted mb-6">{message}</p>
            <p className="text-xs text-muted">Redirecting you to login…</p>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle className="w-12 h-12 text-rose mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-ivory mb-2">Verification failed</h1>
            <p className="text-sm text-muted mb-6">{message}</p>
            <button
              onClick={handleResend}
              disabled={isResending}
              className="w-full mb-3 py-2.5 rounded-xl bg-gold text-void font-semibold text-sm hover:bg-amber transition-colors disabled:opacity-50"
            >
              {isResending ? 'Sending…' : 'Resend verification email'}
            </button>
            <Link href="/login" className="text-xs text-fern hover:underline">
              Back to login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
