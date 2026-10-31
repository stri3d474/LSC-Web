import type { AuditEntry } from '@lsc/api-client';
import { Button, DataTable, StatusBadge, type Column } from '@lsc/ui';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { t } from '../i18n';
import { verifyChain } from '../audit/verifyChain';

export function Audit() {
  const { api } = useAuth();
  const [verdict, setVerdict] = useState<'unknown' | 'ok' | 'broken'>('unknown');

  const audit = useQuery({ queryKey: ['audit'], queryFn: () => api.listAudit() });

  async function onVerify() {
    const entries = audit.data?.entries ?? [];
    const ok = await verifyChain(entries);
    setVerdict(ok ? 'ok' : 'broken');
  }

  const columns: Column<AuditEntry>[] = [
    { key: 'at', header: t.audit.date, render: (r) => r.at },
    { key: 'actor', header: t.audit.actor, render: (r) => r.actor },
    { key: 'action', header: t.audit.action, render: (r) => r.action },
    { key: 'target', header: 'Objetivo', render: (r) => r.target ?? '—' },
  ];

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">{t.audit.title}</h2>

      <div className="mb-4 flex items-center gap-3">
        <Button variant="secondary" onClick={() => void onVerify()}>
          {t.audit.verify}
        </Button>
        {verdict === 'ok' ? <StatusBadge kind="success" label={t.audit.chainOk} /> : null}
        {verdict === 'broken' ? <StatusBadge kind="danger" label={t.audit.chainBroken} /> : null}
      </div>

      {audit.isLoading ? (
        <p>{t.common.loading}</p>
      ) : (
        <DataTable
          columns={columns}
          rows={audit.data?.entries ?? []}
          rowKey={(r) => r.entry_id}
          caption={t.audit.title}
          emptyMessage={t.common.empty}
        />
      )}
    </section>
  );
}
