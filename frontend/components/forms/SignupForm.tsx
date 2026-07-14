'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { UserPlus, Eye, EyeOff } from 'lucide-react';
import { Button } from '@/components/atoms/Button';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import api from '@/lib/api';

interface SignupFormData {
  firstName: string;
  lastName: string;
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export function SignupForm() {
  const router = useRouter();
  const { login } = useAuthStore();
  const { addToast } = useUIStore();
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [formData, setFormData] = useState<SignupFormData>({
    firstName: '',
    lastName: '',
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const validateField = (name: keyof SignupFormData, value: string): string => {
    switch (name) {
      case 'firstName':
        return value.length < 2 ? 'First name must be at least 2 characters' : '';
      case 'lastName':
        return value.length < 2 ? 'Last name must be at least 2 characters' : '';
      case 'username':
        return value.length < 3 ? 'Username must be at least 3 characters' : '';
      case 'email':
        return !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? 'Invalid email address' : '';
      case 'password':
        if (value.length < 8) return 'Password must be at least 8 characters';
        if (!/[A-Z]/.test(value)) return 'Password must contain at least one uppercase letter';
        if (!/\d/.test(value)) return 'Password must contain at least one digit';
        return '';
      case 'confirmPassword':
        return value !== formData.password ? 'Passwords do not match' : '';
      default:
        return '';
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    if (touched[name]) {
      const error = validateField(name as keyof SignupFormData, value);
      setErrors((prev) => ({ ...prev, [name]: error }));
    }
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));
    const error = validateField(name as keyof SignupFormData, value);
    setErrors((prev) => ({ ...prev, [name]: error }));
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    (Object.keys(formData) as Array<keyof SignupFormData>).forEach((key) => {
      const error = validateField(key, formData[key]);
      if (error) newErrors[key] = error;
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    setIsLoading(true);
    try {
      await api.post('/auth/register', {
        firstName: formData.firstName,
        lastName: formData.lastName,
        username: formData.username,
        email: formData.email,
        password: formData.password,
      });

      // Auto-login after registration
      await login(formData.email, formData.password);
      addToast({ type: 'success', message: 'Account created successfully!' });
      router.push('/dashboard');
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Registration failed. Please try again.';
      if (detail.toLowerCase().includes('username')) {
        setErrors({ username: detail });
      } else if (detail.toLowerCase().includes('email')) {
        setErrors({ email: detail });
      } else {
        setErrors({ general: detail });
      }
      addToast({ type: 'error', message: detail });
    } finally {
      setIsLoading(false);
    }
  };

  const inputClass = (fieldName: string) =>
    `w-full bg-white/60 border rounded-button px-3.5 py-2.5 text-sm text-void placeholder:text-muted focus:outline-none focus:border-gold/50 transition-colors ${
      errors[fieldName] ? 'border-rose' : 'border-void/10'
    }`;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Title */}
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-void mb-1">Create Account</h2>
        <p className="text-sm text-muted">Start building your AI assistant</p>
      </div>

      {/* General error */}
      {errors.general && (
        <div className="p-3 rounded-xl bg-rose/10 border border-rose/20 text-sm text-rose text-center">
          {errors.general}
        </div>
      )}

      {/* Name fields */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-void/80 mb-1.5">First Name</label>
          <input
            type="text"
            name="firstName"
            value={formData.firstName}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="John"
            className={inputClass('firstName')}
          />
          {errors.firstName && <p className="mt-1 text-xs text-rose">{errors.firstName}</p>}
        </div>
        <div>
          <label className="block text-xs font-semibold text-void/80 mb-1.5">Last Name</label>
          <input
            type="text"
            name="lastName"
            value={formData.lastName}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Doe"
            className={inputClass('lastName')}
          />
          {errors.lastName && <p className="mt-1 text-xs text-rose">{errors.lastName}</p>}
        </div>
      </div>

      {/* Username */}
      <div>
        <label className="block text-xs font-semibold text-void/80 mb-1.5">Username</label>
        <input
          type="text"
          name="username"
          value={formData.username}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder="johndoe"
          className={inputClass('username')}
        />
        {errors.username && <p className="mt-1 text-xs text-rose">{errors.username}</p>}
      </div>

      {/* Email */}
      <div>
        <label className="block text-xs font-semibold text-void/80 mb-1.5">Email</label>
        <input
          type="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder="you@example.com"
          className={inputClass('email')}
        />
        {errors.email && <p className="mt-1 text-xs text-rose">{errors.email}</p>}
      </div>

      {/* Password */}
      <div>
        <label className="block text-xs font-semibold text-void/80 mb-1.5">Password</label>
        <div className="relative">
          <input
            type={showPassword ? "text" : "password"}
            name="password"
            value={formData.password}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Min 8 characters"
            className={`${inputClass('password')} pr-10`}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-void transition-colors"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {errors.password && <p className="mt-1 text-xs text-rose">{errors.password}</p>}
      </div>

      {/* Confirm Password */}
      <div>
        <label className="block text-xs font-semibold text-void/80 mb-1.5">Confirm Password</label>
        <div className="relative">
          <input
            type={showPassword ? "text" : "password"}
            name="confirmPassword"
            value={formData.confirmPassword}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Repeat password"
            className={`${inputClass('confirmPassword')} pr-10`}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-void transition-colors"
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {errors.confirmPassword && (
          <p className="mt-1 text-xs text-rose">{errors.confirmPassword}</p>
        )}
      </div>

      {/* Submit */}
      <Button
        type="submit"
        fullWidth
        isLoading={isLoading}
        icon={UserPlus}
      >
        Create Account
      </Button>

      {/* Login link */}
      <p className="text-center text-xs text-muted mt-4">
        Already have an account?{' '}
        <Link href="/login" className="text-gold hover:underline font-medium">
          Sign in
        </Link>
      </p>
    </form>
  );
}
