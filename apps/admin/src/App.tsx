import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth/AuthProvider';
import { Layout } from './Layout';
import { RoleGuard } from './RoleGuard';
import { Audit } from './screens/Audit';
import { Corrections } from './screens/Corrections';
import { Metrics } from './screens/Metrics';
import { Models } from './screens/Models';
import { Organizations } from './screens/Organizations';
import { SignIn } from './screens/SignIn';
import { Vocabulary } from './screens/Vocabulary';
import { t } from './i18n';

export function App() {
  const { status } = useAuth();

  if (status === 'loading') {
    return <p className="p-6">{t.common.loading}</p>;
  }
  if (status !== 'signed_in') {
    return <SignIn />;
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/corrections" replace />} />
        <Route
          path="/models"
          element={
            <RoleGuard roles={['admin']}>
              <Models />
            </RoleGuard>
          }
        />
        <Route
          path="/vocabulary"
          element={
            <RoleGuard roles={['admin', 'reviewer']}>
              <Vocabulary />
            </RoleGuard>
          }
        />
        <Route
          path="/corrections"
          element={
            <RoleGuard roles={['admin', 'reviewer']}>
              <Corrections />
            </RoleGuard>
          }
        />
        <Route
          path="/organizations"
          element={
            <RoleGuard roles={['admin', 'institution_admin']}>
              <Organizations />
            </RoleGuard>
          }
        />
        <Route
          path="/audit"
          element={
            <RoleGuard roles={['admin']}>
              <Audit />
            </RoleGuard>
          }
        />
        <Route
          path="/metrics"
          element={
            <RoleGuard roles={['admin', 'reviewer']}>
              <Metrics />
            </RoleGuard>
          }
        />
        <Route path="*" element={<Navigate to="/corrections" replace />} />
      </Route>
    </Routes>
  );
}
