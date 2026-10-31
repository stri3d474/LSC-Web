import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  children: ReactNode;
}

// Accessible button: className-driven styling (Tailwind), keyboard focusable,
// 44px min height. No inline styles (strict CSP).
export function Button({ variant = 'primary', children, className = '', ...rest }: ButtonProps) {
  const base =
    'inline-flex min-h-[44px] items-center justify-center rounded px-4 py-2 text-base font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50';
  const variants: Record<string, string> = {
    primary: 'bg-sky-800 text-white hover:bg-sky-900 focus-visible:ring-sky-700',
    secondary: 'border border-slate-400 text-slate-800 hover:bg-slate-100',
    danger: 'bg-red-700 text-white hover:bg-red-800 focus-visible:ring-red-600',
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}
