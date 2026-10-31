import type { InputHTMLAttributes } from 'react';
import { useId } from 'react';

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

// Labelled input with an associated error message (aria-describedby).
export function TextField({ label, error, className = '', ...rest }: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        className={`min-h-[44px] rounded border border-slate-400 px-3 py-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-700 ${className}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        {...rest}
      />
      {error ? (
        <span id={errorId} className="text-sm text-red-700" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
