import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { UserProfile } from '@/types';
import {
  api,
  ApiError,
  UNAUTHORIZED_EVENT,
  type LoginPayload,
  type RegisterPayload,
} from '@/lib/api';

type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

interface AuthValue {
  user: UserProfile | null;
  status: AuthStatus;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  /** Replace the cached profile after a profile/telegram mutation. */
  setUser: (user: UserProfile) => void;
  /** Re-fetch the current profile from the server. */
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [user, setUserState] = useState<UserProfile | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');

  const applyUser = useCallback((profile: UserProfile) => {
    setUserState(profile);
    setStatus('authenticated');
  }, []);

  const clearUser = useCallback(() => {
    setUserState(null);
    setStatus('anonymous');
  }, []);

  const refresh = useCallback(async () => {
    try {
      applyUser(await api.me());
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearUser();
        return;
      }
      throw error;
    }
  }, [applyUser, clearUser]);

  // Probe the session once on mount.
  useEffect(() => {
    void (async () => {
      try {
        applyUser(await api.me());
      } catch {
        clearUser();
      }
    })();
  }, [applyUser, clearUser]);

  // Any 401 from the API client clears the session globally.
  useEffect(() => {
    const handleUnauthorized = (): void => clearUser();
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
  }, [clearUser]);

  const login = useCallback(
    async (payload: LoginPayload) => applyUser(await api.login(payload)),
    [applyUser],
  );

  const register = useCallback(
    async (payload: RegisterPayload) => applyUser(await api.register(payload)),
    [applyUser],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clearUser();
    }
  }, [clearUser]);

  const value = useMemo<AuthValue>(
    () => ({ user, status, login, register, logout, setUser: applyUser, refresh }),
    [user, status, login, register, logout, applyUser, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
