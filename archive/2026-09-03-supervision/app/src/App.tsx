import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { I18nProvider } from '@/context/I18nContext';
import { ThemeProvider } from '@/context/ThemeContext';
import { ToastProvider } from '@/context/ToastContext';
import { RealtimeProvider } from '@/context/RealtimeContext';
import { RequireAnon, RequireAuth } from '@/components/RouteGuards';
import { AppShell } from '@/components/AppShell';
import { ToastViewport } from '@/components/ToastViewport';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { ManagedListPage } from '@/pages/ManagedListPage';
import { ManagedDetailPage } from '@/pages/ManagedDetailPage';
import { ManagersPage } from '@/pages/ManagersPage';
import { LinkPage } from '@/pages/LinkPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

/** Authenticated frame: opens the SSE stream and wraps pages in the app shell. */
function AuthenticatedLayout({ children }: { children: React.ReactNode }): JSX.Element {
  const { status } = useAuth();
  return (
    <RealtimeProvider enabled={status === 'authenticated'}>
      <AppShell>{children}</AppShell>
    </RealtimeProvider>
  );
}

function ProtectedRoutes(): JSX.Element {
  return (
    <RequireAuth>
      <AuthenticatedLayout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/managed" element={<ManagedListPage />} />
          <Route path="/managed/:userId" element={<ManagedDetailPage />} />
          <Route path="/managers" element={<ManagersPage />} />
          <Route path="/link" element={<LinkPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthenticatedLayout>
    </RequireAuth>
  );
}

export function App(): JSX.Element {
  return (
    <ThemeProvider>
      <I18nProvider>
        <ToastProvider>
          {/* Vite base '/app/' → SPA history routes live under /app/. */}
          <BrowserRouter basename="/app">
            <AuthProvider>
              <Routes>
                <Route
                  path="/login"
                  element={
                    <RequireAnon>
                      <LoginPage />
                    </RequireAnon>
                  }
                />
                <Route
                  path="/register"
                  element={
                    <RequireAnon>
                      <RegisterPage />
                    </RequireAnon>
                  }
                />
                <Route path="/*" element={<ProtectedRoutes />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
              <ToastViewport />
            </AuthProvider>
          </BrowserRouter>
        </ToastProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
