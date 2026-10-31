import type { ReactNode } from 'react';
import { useEffect, useRef } from 'react';

interface DialogProps {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
}

// Modal dialog using the native <dialog> element for built-in focus trapping
// and Esc handling. No inline scripts/styles (strict CSP).
export function Dialog({ open, title, children, onClose }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="rounded-lg p-0 backdrop:bg-black/40"
      aria-label={title}
      onClose={onClose}
      onCancel={onClose}
    >
      <div className="w-[32rem] max-w-[90vw] p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-800">{title}</h2>
        {children}
      </div>
    </dialog>
  );
}
