import type { ModelPackage } from '@lsc/api-client';
import { ApiError } from '@lsc/api-client';
import { Button, DataTable, StatusBadge, TextField, type BadgeKind, type Column } from '@lsc/ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { errorMessage, t } from '../i18n';

function statusKind(status: string): BadgeKind {
  if (status === 'active') return 'success';
  if (status === 'draft') return 'neutral';
  return 'warning';
}

export function Models() {
  const { api } = useAuth();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dataKey, setDataKey] = useState('');

  const models = useQuery({
    queryKey: ['models'],
    queryFn: () => api.listModels(),
  });

  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('no file');
      return api.uploadModel(file, dataKey);
    },
    onSuccess: () => {
      setFile(null);
      setDataKey('');
      void qc.invalidateQueries({ queryKey: ['models'] });
    },
    onError: (e) => setError(e instanceof ApiError ? errorMessage(e.code) : errorMessage('unknown')),
  });

  const activate = useMutation({
    mutationFn: (v: string) =>
      api.activateModel(v, { channel: 'stable', rollout_bp: 10000 }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['models'] }),
    onError: (e) => setError(e instanceof ApiError ? errorMessage(e.code) : errorMessage('unknown')),
  });

  const deactivate = useMutation({
    mutationFn: (v: string) => api.deactivateModel(v),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['models'] }),
    onError: (e) => setError(e instanceof ApiError ? errorMessage(e.code) : errorMessage('unknown')),
  });

  const columns: Column<ModelPackage>[] = [
    { key: 'version', header: t.models.version, render: (r) => r.package_version },
    { key: 'profile', header: t.models.profile, render: (r) => r.profile },
    {
      key: 'status',
      header: t.models.status,
      render: (r) => <StatusBadge kind={statusKind(r.status)} label={r.status} />,
    },
    { key: 'channel', header: t.models.channel, render: (r) => r.channel ?? '—' },
    { key: 'rollout', header: t.models.rollout, render: (r) => `${r.rollout_bp / 100}%` },
    {
      key: 'actions',
      header: '',
      render: (r) =>
        r.status === 'active' ? (
          <Button variant="secondary" onClick={() => deactivate.mutate(r.package_version)}>
            {t.models.deactivate}
          </Button>
        ) : (
          <Button onClick={() => activate.mutate(r.package_version)}>{t.models.activate}</Button>
        ),
    },
  ];

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">{t.models.title}</h2>

      <form
        className="mb-6 flex items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          upload.mutate();
        }}
      >
        <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
          {t.models.packageFile}
          <input
            type="file"
            accept=".zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <TextField
          label={t.models.dataKey}
          value={dataKey}
          onChange={(e) => setDataKey(e.target.value)}
        />
        <Button type="submit" disabled={!file || !dataKey || upload.isPending}>
          {t.models.upload}
        </Button>
      </form>

      {error ? (
        <p className="mb-4 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}

      {models.isLoading ? (
        <p>{t.common.loading}</p>
      ) : (
        <DataTable
          columns={columns}
          rows={models.data?.packages ?? []}
          rowKey={(r) => r.package_version}
          caption={t.models.title}
          emptyMessage={t.common.empty}
        />
      )}
    </section>
  );
}
