'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { LogIn, Eye, EyeOff } from 'lucide-react';
import { Button } from '@/components/atoms/Button';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import api from '@/lib/api';

interface LoginFormData {
  username: string;
  password: string;
  rememberMe: boolean;
}

export function LoginForm() {
  const router = useRouter();
  const { login } = useAuthStore();
  const { addToast } = useUIStore();
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [resendEmail, setResendEmail] = useState<string | null>(null);
  const [formData, setFormData] = useState<LoginFormData>({
    username: '',
    password: '',
    rememberMe: false,
  });

  // Turns an axios failure into something the person reading it can act on.
  const describeLoginError = (err: any): string => {
    if (err?.code === 'ECONNABORTED') {
      return 'The server took too long to respond. Please try again.';
    }
    if (!err?.response) {
      return "Can't reach the server. Check that the API is running, then try again.";
    }

    const { status, data } = err.response;
    const detail = data?.detail;

    // Structured detail object (e.g. from 403 unverified gate)
    if (detail && typeof detail === 'object') {
      return detail.message || 'Sign in failed. Please try again.';
    }

    if (status === 401) return typeof detail === 'string' ? detail : 'Incorrect email/username or password.';
    if (status === 400) return typeof detail === 'string' ? detail : 'This account cannot sign in right now.';
    if (status === 422) return 'Please enter both your email/username and password.';
    if (status >= 500) return 'The server hit an error while signing you in. Please try again.';
    return typeof detail === 'string' ? detail : 'Sign in failed. Please try again.';
  };

  const handleResendVerification = async () => {
    if (!resendEmail) return;
    setIsResending(true);
    try {
      await api.post('/auth/resend-verification', { email: resendEmail });
      addToast({ type: 'success', message: 'Verification email sent! Check your inbox.' });
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Could not send email. Please try again.';
      addToast({ type: 'error', message: typeof msg === 'string' ? msg : 'Please wait before requesting another email.' });
    } finally {
      setIsResending(false);
    }
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.username.trim()) {
      newErrors.username = 'Username or email is required';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    setIsLoading(true);
    setResendEmail(null);
    try {
      await login(formData.username, formData.password);
      addToast({ type: 'success', message: 'Welcome back!' });
      router.push('/dashboard');
    } catch (err: any) {
      const data = err?.response?.data;

      // Hard gate: unverified account — surface resend button
      if (err?.response?.status === 403 && data?.detail?.action === 'resend_verification') {
        setResendEmail(formData.username.includes('@') ? formData.username : '');
        setErrors({ general: data.detail.message });
        addToast({ type: 'error', message: data.detail.message });
      } else {
        const message = describeLoginError(err);
        setErrors({ general: message });
        addToast({ type: 'error', message });
      }
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Title */}
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-void mb-1">Welcome Back</h2>
        <p className="text-sm text-muted">Sign in to your account</p>
      </div>

      {/* General error + optional resend button */}
      {errors.general && (
        <div className="p-3 rounded-xl bg-rose/10 border border-rose/20 text-sm text-rose text-center">
          <p>{errors.general}</p>
          {resendEmail !== null && (
            <button
              type="button"
              onClick={handleResendVerification}
              disabled={isResending}
              className="mt-2 text-xs font-semibold underline text-rose/80 hover:text-rose disabled:opacity-50"
            >
              {isResending ? 'Sending…' : 'Resend verification email'}
            </button>
          )}
        </div>
      )}

      {/* Username */}
      <div>
        <label className="block text-xs font-semibold text-void/80 mb-1.5">
          Email or Username
        </label>
        <input
          type="text"
          value={formData.username}
          onChange={(e) => setFormData({ ...formData, username: e.target.value })}
          placeholder="you@example.com"
          className="w-full bg-white/60 border border-void/10 rounded-button px-3.5 py-2.5 text-sm text-void placeholder:text-muted focus:outline-none focus:border-gold/50 transition-colors"
        />
        {errors.username && (
          <p className="mt-1 text-xs text-rose">{errors.username}</p>
        )}
      </div>

      {/* Password */}
      <div>
        <label className="block text-xs font-semibold text-void/80 mb-1.5">
          Password
        </label>
        <div className="relative">
          <input
            type={showPassword ? "text" : "password"}
            value={formData.password}
            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            placeholder="••••••••"
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
        {errors.password && (
          <p className="mt-1 text-xs text-rose">{errors.password}</p>
        )}
      </div>

      {/* Remember me + Forgot password */}
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={formData.rememberMe}
            onChange={(e) => setFormData({ ...formData, rememberMe: e.target.checked })}
            className="w-4 h-4 rounded border-void/20 text-gold focus:ring-gold"
          />
          <span className="text-xs text-void/70">Remember me</span>
        </label>
        <Link
          href="/forgot-password"
          className="text-xs text-gold hover:underline"
        >
          Forgot password?
        </Link>
      </div>

      {/* Submit */}
      <Button
        type="submit"
        fullWidth
        isLoading={isLoading}
        icon={LogIn}
      >
        Sign In
      </Button>

      {/* Sign up link */}
      <p className="text-center text-xs text-muted mt-4">
        Don&apos;t have an account?{' '}
        <Link href="/signup" className="text-gold hover:underline font-medium">
          Create one
        </Link>
      </p>
    </form>
  );
}
