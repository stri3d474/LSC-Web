import { Button } from '@lsc/ui';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from './auth/AuthProvider';
import { t } from './i18n';

const navItems = [
  { to: '/models', label: t.nav.models, roles: ['admin'] },
  { to: '/vocabulary', label: t.nav.vocabulary, roles: ['admin', 'reviewer'] },
  { to: '/corrections', label: t.nav.corrections, roles: ['admin', 'reviewer'] },
  { to: '/organizations', label: t.nav.organizations, roles: ['admin', 'institution_admin'] },
  { to: '/audit', label: t.nav.audit, roles: ['admin'] },
  { to: '/metrics', label: t.nav.metrics, roles: ['admin', 'reviewer'] },
] as const;

export function Layout() {
  const { signOut, hasRole, me } = useAuth();
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <nav aria-label="Principal" className="w-56 border-r border-slate-200 bg-white p-4">
        <h1 className="mb-6 text-lg font-bold text-sky-900">{t.appTitle}</h1>
        <ul className="flex flex-col gap-1">
          {navItems
            .filter((item) => hasRole(...(item.roles as unknown as Parameters<typeof hasRole>)))
            .map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `block rounded px-3 py-2 text-sm ${
                      isActive ? 'bg-sky-100 font-semibold text-sky-900' : 'text-slate-700 hover:bg-slate-100'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
        </ul>
        <div className="mt-8 border-t border-slate-200 pt-4">
          <p className="mb-2 truncate text-xs text-slate-500">{me?.uid}</p>
          <Button variant="secondary" onClick={() => void signOut()}>
            {t.nav.signOut}
          </Button>
        </div>
      </nav>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
