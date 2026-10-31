import type { Concept } from '@lsc/api-client';
import { DataTable, StatusBadge, type Column } from '@lsc/ui';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthProvider';
import { t } from '../i18n';

export function Vocabulary() {
  const { api } = useAuth();
  const vocab = useQuery({ queryKey: ['vocabulary'], queryFn: () => api.vocabulary(0) });

  const columns: Column<Concept>[] = [
    { key: 'concept', header: t.vocabulary.concept, render: (r) => r.concept_id },
    { key: 'gloss', header: t.vocabulary.gloss, render: (r) => r.gloss },
    { key: 'es', header: t.vocabulary.esText, render: (r) => r.es_text },
    {
      key: 'variants',
      header: 'Variantes',
      render: (r) => r.variants.map((v) => `${v.variant_id} (${v.tier})`).join(', '),
    },
    {
      key: 'state',
      header: 'Estado',
      render: (r) =>
        r.deleted ? <StatusBadge kind="danger" label="eliminado" /> : <StatusBadge kind="success" label="activo" />,
    },
  ];

  return (
    <section>
      <h2 className="mb-2 text-xl font-semibold">{t.vocabulary.title}</h2>
      <p className="mb-4 text-sm text-slate-600">
        {t.vocabulary.version}: {vocab.data?.vocabulary_version ?? '—'}
      </p>
      {vocab.isLoading ? (
        <p>{t.common.loading}</p>
      ) : (
        <DataTable
          columns={columns}
          rows={vocab.data?.concepts ?? []}
          rowKey={(r) => r.concept_id}
          caption={t.vocabulary.title}
          emptyMessage={t.common.empty}
        />
      )}
    </section>
  );
}
