import { ApiError } from '@lsc/api-client';
import { Button, Dialog, TextField } from '@lsc/ui';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { errorMessage, t } from '../i18n';

export function Organizations() {
  const { api } = useAuth();
  const [orgId, setOrgId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);

  const issue = useMutation({
    mutationFn: () => api.issueVerificationCode(orgId),
    onSuccess: (res) => setCode(res.code),
    onError: (e) => setError(e instanceof ApiError ? errorMessage(e.code) : errorMessage('unknown')),
  });

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">{t.organizations.title}</h2>

      <form
        className="flex items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          issue.mutate();
        }}
      >
        <TextField
          label={t.organizations.orgId}
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
        />
        <Button type="submit" disabled={!orgId || issue.isPending}>
          {t.organizations.issueCode}
        </Button>
      </form>

      {error ? (
        <p className="mt-4 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}

      <Dialog open={code !== null} title={t.organizations.issueCode} onClose={() => setCode(null)}>
        <p className="mb-3 text-sm text-amber-800">{t.organizations.codeOnce}</p>
        <code className="block break-all rounded bg-slate-100 p-3 text-sm">{code}</code>
        <div className="mt-4 flex gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              if (code) void navigator.clipboard.writeText(code);
            }}
          >
            {t.organizations.copy}
          </Button>
          <Button onClick={() => setCode(null)}>{t.common.confirm}</Button>
        </div>
      </Dialog>
    </section>
  );
}
