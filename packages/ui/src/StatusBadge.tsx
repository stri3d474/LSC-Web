export type BadgeKind = 'neutral' | 'success' | 'warning' | 'danger';

interface StatusBadgeProps {
  kind: BadgeKind;
  label: string;
}

// Status conveyed by both color and text (never color alone, accessibility).
export function StatusBadge({ kind, label }: StatusBadgeProps) {
  const styles: Record<BadgeKind, string> = {
    neutral: 'bg-slate-200 text-slate-800',
    success: 'bg-green-200 text-green-900',
    warning: 'bg-amber-200 text-amber-900',
    danger: 'bg-red-200 text-red-900',
  };
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${styles[kind]}`}>
      {label}
    </span>
  );
}
