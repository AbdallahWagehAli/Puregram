import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui';
import { LogoMark } from '@/components/Logo';

/** Full-screen brand splash while the session probe is in flight. */
function SessionSplash(): JSX.Element {
  return (
    <div className="grid min-h-screen place-items-center">
      <div className="flex flex-col items-center gap-4">
        <LogoMark size={56} />
        <Spinner size={24} />
      </div>
    </div>
  );
}

/** Renders children only when authenticated; otherwise redirects to /login. */
export function RequireAuth({ children }: { children: ReactNode }): JSX.Element {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') return <SessionSplash />;
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

/** Keeps authenticated users out of the login/register screens. */
export function RequireAnon({ children }: { children: ReactNode }): JSX.Element {
  const { status } = useAuth();

  if (status === 'loading') return <SessionSplash />;
  if (status === 'authenticated') return <Navigate to="/" replace />;
  return <>{children}</>;
}
