'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { LogIn, Eye, EyeOff } from 'lucide-react';
import { Button } from '@/components/atoms/Button';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';

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
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formData, setFormData] = useState<LoginFormData>({
    username: '',
    password: '',
    rememberMe: false,
  });

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
    try {
      await login(formData.username, formData.password);
      addToast({ type: 'success', message: 'Welcome back!' });
      router.push('/dashboard');
    } catch {
      setErrors({ general: 'Invalid credentials. Please try again.' });
      addToast({ type: 'error', message: 'Login failed. Check your credentials.' });
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

      {/* General error */}
      {errors.general && (
        <div className="p-3 rounded-xl bg-rose/10 border border-rose/20 text-sm text-rose text-center">
          {errors.general}
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
