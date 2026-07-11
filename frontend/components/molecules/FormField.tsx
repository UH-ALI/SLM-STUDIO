import { classNames } from '@/lib/utils';

interface FormFieldProps {
  label: string;
  error?: string;
  children: React.ReactNode;
  required?: boolean;
  className?: string;
  htmlFor?: string;
}

export function FormField({
  label,
  error,
  children,
  required = false,
  className,
  htmlFor,
}: FormFieldProps) {
  return (
    <div className={classNames('w-full', className)}>
      <label
        htmlFor={htmlFor}
        className="block text-[0.75rem] font-semibold uppercase tracking-[0.08em] text-fern mb-1.5"
      >
        {label}
        {required && <span className="text-rose ml-1">*</span>}
      </label>
      {children}
      {error && (
        <p
          className="mt-1 text-xs text-rose animate-[shake_0.3s_ease-in-out]"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
}
