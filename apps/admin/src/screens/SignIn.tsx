import { ApiError } from '@lsc/api-client';
import { Button } from '@lsc/ui';
import { useState } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { errorMessage, t } from '../i18n';

export function SignIn() {
  const { signIn, status } = useAuth();
  const [error, setError] = useState<string | null>(null);

  async function onSignIn() {
    setError(null);
    try {
      await signIn();
    } catch (e) {
      setError(e instanceof ApiError ? errorMessage(e.code) : errorMessage('unknown'));
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-96 rounded-lg bg-white p-8 shadow">
        <h1 className="mb-6 text-xl font-bold text-sky-900">{t.auth.signInTitle}</h1>
        <Button onClick={() => void onSignIn()}>{t.auth.signInButton}</Button>
        {status === 'mfa_required' ? (
          <p className="mt-4 text-sm text-amber-700" role="alert">
            {t.auth.mfaRequired}
          </p>
        ) : null}
        {error ? (
          <p className="mt-4 text-sm text-red-700" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
