import type { Correction, CorrectionStatus } from '@lsc/api-client';
import { ApiError } from '@lsc/api-client';
import { Button, DataTable, StatusBadge, type Column } from '@lsc/ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { SkeletonPlayer } from '../components/SkeletonPlayer';
import { useAuth } from '../auth/AuthProvider';
import { errorMessage, t } from '../i18n';

const STATUSES: CorrectionStatus[] = ['pending', 'approved', 'rejected', 'merged'];

export function Corrections() {
  const { api } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState<CorrectionStatus>('pending');
  const [error, setError] = useState<string | null>(null);
  const [exportUrl, setExportUrl] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ['corrections', status],
    queryFn: () => api.listCorrections(status),
  });

  const review = useMutation({
    mutationFn: (v: { id: string; approve: boolean }) =>
      api.reviewCorrection(v.id, { approve: v.approve, reason: v.approve ? null : 'rechazado por revisor' }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['corrections'] }),
    onError: (e) => setError(e instanceof ApiError ? errorMessage(e.code) : errorMessage('unknown')),
  });

  const exportApproved = useMutation({
    mutationFn: () => api.exportCorrections(),
    onSuccess: (res) => setExportUrl(res.url),
    onError: (e) => setError(e instanceof ApiError ? errorMessage(e.code) : errorMessage('unknown')),
  });

  const columns: Column<Correction>[] = [
    {
      key: 'skeleton',
      header: '',
      // The list endpoint does not return the landmark blob (privacy); the
      // player renders a placeholder. A detail fetch would supply the sequence.
      render: () => <SkeletonPlayer sequence={null} frameVectorSize={0} frames={0} />,
    },
    { key: 'predicted', header: t.corrections.predicted, render: (r) => r.predicted_variant_id },
    { key: 'proposed', header: t.corrections.proposed, render: (r) => r.proposed_variant_id ?? '—' },
    { key: 'region', header: t.corrections.region, render: (r) => r.region },
    { key: 'context', header: t.corrections.context, render: (r) => r.context },
    {
      key: 'status',
      header: t.corrections.filterStatus,
      render: (r) => <StatusBadge kind="neutral" label={r.status} />,
    },
    {
      key: 'actions',
      header: '',
      render: (r) =>
        r.status === 'pending' ? (
          <div className="flex gap-2">
            <Button onClick={() => review.mutate({ id: r.correction_id, approve: true })}>
              {t.corrections.approve}
            </Button>
            <Button variant="danger" onClick={() => review.mutate({ id: r.correction_id, approve: false })}>
              {t.corrections.reject}
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">{t.corrections.title}</h2>

      <div className="mb-4 flex items-center gap-3">
        <label className="text-sm font-medium">
          {t.corrections.filterStatus}{' '}
          <select
            className="rounded border border-slate-400 px-2 py-1"
            value={status}
            onChange={(e) => setStatus(e.target.value as CorrectionStatus)}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <Button variant="secondary" onClick={() => exportApproved.mutate()}>
          {t.corrections.export}
        </Button>
        {exportUrl ? (
          <a className="text-sm text-sky-800 underline" href={exportUrl} rel="noreferrer">
            JSONL
          </a>
        ) : null}
      </div>

      {error ? (
        <p className="mb-4 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}

      {list.isLoading ? (
        <p>{t.common.loading}</p>
      ) : (
        <DataTable
          columns={columns}
          rows={list.data?.corrections ?? []}
          rowKey={(r) => r.correction_id}
          caption={t.corrections.title}
          emptyMessage={t.common.empty}
        />
      )}
    </section>
  );
}
