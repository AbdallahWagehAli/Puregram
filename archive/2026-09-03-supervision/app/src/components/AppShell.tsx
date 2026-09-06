import { useState, type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useI18n } from '@/context/I18nContext';
import { useAuth } from '@/context/AuthContext';
import { useRealtime } from '@/context/RealtimeContext';
import { LogoLockup } from '@/components/Logo';
import { LangToggle, ThemeToggle } from '@/components/Controls';
import {
  DashboardIcon,
  LinkIcon,
  LogoutIcon,
  MenuIcon,
  SettingsIcon,
  ShieldIcon,
  UsersIcon,
  XIcon,
} from '@/components/icons';
import type { MessageKey } from '@/i18n/dictionary';

interface NavItem {
  to: string;
  labelKey: MessageKey;
  /** Bottom-bar label — a tab is ~70px wide, so the sidebar wording won't fit. */
  shortKey: MessageKey;
  icon: (props: { size?: number }) => JSX.Element;
  /** When set, reads a live badge count from realtime state. */
  badge?: 'incoming';
}

const NAV_ITEMS: readonly NavItem[] = [
  { to: '/', labelKey: 'nav.dashboard', shortKey: 'nav.dashboardShort', icon: DashboardIcon },
  { to: '/managed', labelKey: 'nav.managed', shortKey: 'nav.managedShort', icon: ShieldIcon },
  {
    to: '/managers',
    labelKey: 'nav.managers',
    shortKey: 'nav.managersShort',
    icon: UsersIcon,
    badge: 'incoming',
  },
  { to: '/link', labelKey: 'nav.link', shortKey: 'nav.linkShort', icon: LinkIcon },
  { to: '/settings', labelKey: 'nav.settings', shortKey: 'nav.settingsShort', icon: SettingsIcon },
];

function NavBadge({ count }: { count: number }): JSX.Element | null {
  if (count <= 0) return null;
  return (
    <span className="grid min-w-5 place-items-center rounded-full bg-grad px-1.5 text-[11px] font-bold text-white">
      {count > 99 ? '99+' : count}
    </span>
  );
}

/**
 * Phone navigation: a fixed bottom tab bar, the shape people expect from an app
 * rather than a website. It carries the same five destinations as the sidebar,
 * so the drawer is left to the account panel.
 */
function BottomNav(): JSX.Element {
  const { t } = useI18n();
  const { incomingCount } = useRealtime();

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-[var(--nav-bg-2)] backdrop-blur lg:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <ul className="mx-auto flex max-w-lg items-stretch">
        {NAV_ITEMS.map(({ to, shortKey, icon: Icon, badge }) => (
          <li key={to} className="flex-1">
            <NavLink
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 px-1 pb-2 pt-2.5 text-[11px] font-bold transition-colors ${
                  isActive ? 'text-brand-red' : 'text-dim'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`relative grid h-8 w-14 place-items-center rounded-full transition-colors ${
                      isActive ? 'bg-[rgba(46,158,79,.16)]' : ''
                    }`}
                  >
                    <Icon size={20} />
                    {badge === 'incoming' && incomingCount > 0 && (
                      <span className="absolute -top-0.5 ltr:right-2 rtl:left-2 grid h-4 min-w-4 place-items-center rounded-full bg-grad px-1 text-[10px] font-bold text-white">
                        {incomingCount > 9 ? '9+' : incomingCount}
                      </span>
                    )}
                  </span>
                  <span className="max-w-full truncate">{t(shortKey)}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }): JSX.Element {
  const { t } = useI18n();
  const { incomingCount } = useRealtime();

  return (
    <nav className="flex flex-col gap-1" aria-label="Primary">
      {NAV_ITEMS.map(({ to, labelKey, icon: Icon, badge }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-xl px-4 py-3 text-[15px] font-semibold transition-colors ${
              isActive
                ? 'bg-[linear-gradient(120deg,rgba(63,183,104,.16),rgba(30,122,60,.1))] text-text shadow-[inset_0_0_0_1px_var(--line-2)]'
                : 'text-muted hover:bg-[var(--surface)] hover:text-text'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <span className={isActive ? 'text-brand-red' : ''}>
                <Icon size={20} />
              </span>
              <span className="flex-1">{t(labelKey)}</span>
              {badge === 'incoming' && <NavBadge count={incomingCount} />}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function UserCard(): JSX.Element {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  const handleLogout = async (): Promise<void> => {
    await logout();
    navigate('/login', { replace: true });
  };

  const name = user?.display_name?.trim() || user?.email || '';
  const initial = name.charAt(0).toUpperCase() || '?';

  return (
    <div className="mt-auto flex items-center gap-3 rounded-xl border border-line bg-[var(--surface)] p-3">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-grad font-en text-base font-bold text-white">
        {initial}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-bold text-text">{name}</span>
        <span className="block truncate font-en text-xs text-dim">{user?.email}</span>
      </span>
      <button
        type="button"
        onClick={handleLogout}
        className="grid h-9 w-9 place-items-center rounded-lg text-dim transition-colors hover:bg-bg-2 hover:text-brand-red"
        aria-label={t('nav.logout')}
        title={t('nav.logout')}
      >
        <LogoutIcon size={18} />
      </button>
    </div>
  );
}

/** Responsive app frame: fixed sidebar on desktop, slide-in drawer on mobile. */
export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const { t } = useI18n();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const closeDrawer = (): void => setDrawerOpen(false);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[280px_1fr]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen flex-col gap-6 border-line bg-bg-2 p-5 ltr:border-r rtl:border-l lg:flex">
        <LogoLockup />
        <NavLinks />
        <UserCard />
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={closeDrawer} />
          <aside className="absolute inset-y-0 flex w-72 max-w-[82vw] animate-fade-in flex-col gap-6 bg-bg-2 p-5 shadow-brand ltr:left-0 rtl:right-0">
            <div className="flex items-center justify-between">
              <LogoLockup />
              <button
                type="button"
                onClick={closeDrawer}
                className="grid h-10 w-10 place-items-center rounded-xl border border-line-2 text-text"
                aria-label={t('nav.close')}
              >
                <XIcon size={18} />
              </button>
            </div>
            <NavLinks onNavigate={closeDrawer} />
            <UserCard />
          </aside>
        </div>
      )}

      {/* Main column */}
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-line bg-[var(--nav-bg-2)] px-4 backdrop-blur lg:px-8">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="grid h-10 w-10 place-items-center rounded-xl border border-line-2 text-text lg:hidden"
            aria-label={t('nav.menu')}
          >
            <MenuIcon size={20} />
          </button>
          <div className="lg:hidden">
            <LogoLockup size={32} />
          </div>
          <div className="ms-auto flex items-center gap-2">
            <LangToggle />
            <ThemeToggle />
          </div>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-28 pt-6 lg:px-8 lg:pb-10 lg:pt-10">
          {children}
        </main>
      </div>

      <BottomNav />
    </div>
  );
}
