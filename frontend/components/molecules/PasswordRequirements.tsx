'use client';

import { Check, X } from 'lucide-react';

interface PasswordRequirementsProps {
  password: string;
}

interface Requirement {
  label: string;
  test: (value: string) => boolean;
}

// [FEATURE] Kept in exact sync with the backend's password validator
// (backend/app/schemas.py UserCreate.validate_password) — every rule shown
// green here is guaranteed to pass on submit, and vice versa.
const REQUIREMENTS: Requirement[] = [
  { label: 'At least 8 characters', test: (v) => v.length >= 8 },
  { label: 'One uppercase letter', test: (v) => /[A-Z]/.test(v) },
  { label: 'One digit', test: (v) => /\d/.test(v) },
];

export function PasswordRequirements({ password }: PasswordRequirementsProps) {
  return (
    <ul className="mt-2 space-y-1">
      {REQUIREMENTS.map((req) => {
        const met = req.test(password);
        return (
          <li
            key={req.label}
            className={`flex items-center gap-1.5 text-xs transition-colors duration-200 ${
              met ? 'text-sage' : 'text-muted'
            }`}
          >
            {met ? (
              <Check className="w-3.5 h-3.5 shrink-0" />
            ) : (
              <X className="w-3.5 h-3.5 shrink-0" />
            )}
            {req.label}
          </li>
        );
      })}
    </ul>
  );
}

// Exported so SignupForm can gate submission on "all requirements met"
// without duplicating the rule list.
export function allPasswordRequirementsMet(password: string): boolean {
  return REQUIREMENTS.every((req) => req.test(password));
}
