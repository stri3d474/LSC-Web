import type { Role } from '@lsc/api-client';
import type { ReactNode } from 'react';
import { useAuth } from './auth/AuthProvider';
import { t } from './i18n';

// Route guard mirroring the backend role checks. The backend is the real
// boundary; this prevents showing screens a user cannot use.
export function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { hasRole } = useAuth();
  if (!hasRole(...roles)) {
    return <p className="p-6 text-red-700">{t.auth.accessDenied}</p>;
  }
  return <>{children}</>;
}
