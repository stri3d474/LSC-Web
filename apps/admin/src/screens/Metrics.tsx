import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { t } from '../i18n';

// Aggregate counts only (no personal data).
export function Metrics() {
  const { api } = useAuth();
  const pending = useQuery({
    queryKey: ['metrics', 'pending'],
    queryFn: () => api.listCorrections('pending'),
  });
  const models = useQuery({ queryKey: ['metrics', 'models'], queryFn: () => api.listModels() });

  const activeModels = (models.data?.packages ?? []).filter((p) => p.status === 'active').length;

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">{t.metrics.title}</h2>
      <dl className="grid max-w-md grid-cols-2 gap-4">
        <div className="rounded border border-slate-200 bg-white p-4">
          <dt className="text-sm text-slate-600">{t.metrics.pendingCorrections}</dt>
          <dd className="text-2xl font-semibold">{pending.data?.corrections.length ?? '—'}</dd>
        </div>
        <div className="rounded border border-slate-200 bg-white p-4">
          <dt className="text-sm text-slate-600">{t.metrics.activeModels}</dt>
          <dd className="text-2xl font-semibold">{activeModels}</dd>
        </div>
      </dl>
    </section>
  );
}
