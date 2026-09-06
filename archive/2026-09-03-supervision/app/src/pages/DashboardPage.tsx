import { Link } from 'react-router-dom';
import { useI18n } from '@/context/I18nContext';
import { useAuth } from '@/context/AuthContext';
import { useRealtime } from '@/context/RealtimeContext';
import { api } from '@/lib/api';
import { useAsyncData } from '@/hooks/useAsyncData';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/ui';
import { Skeleton } from '@/components/Skeleton';
import {
  DashboardIcon,
  InboxIcon,
  LinkIcon,
  ShieldIcon,
  UsersIcon,
} from '@/components/icons';
import { formatNumber } from '@/lib/format';
import type { MessageKey } from '@/i18n/dictionary';

interface StatCardProps {
  labelKey: MessageKey;
  value: number | null;
  to: string;
  icon: (props: { size?: number }) => JSX.Element;
  accent: 'red' | 'gold' | 'blue';
}

const ACCENTS: Record<StatCardProps['accent'], string> = {
  red: 'from-[rgba(255,64,64,.16)] to-[rgba(224,31,31,.06)] text-brand-red',
  gold: 'from-[rgba(230,194,74,.16)] to-[rgba(199,154,43,.06)] text-[var(--gold)]',
  blue: 'from-[rgba(74,144,230,.16)] to-[rgba(43,99,199,.06)] text-[#5b9bff]',
};

function StatCard({ labelKey, value, to, icon: Icon, accent }: StatCardProps): JSX.Element {
  const { t, lang } = useI18n();
  return (
    <Link
      to={to}
      className="group rounded-brand-lg border border-line bg-bg-2 p-5 transition-all duration-200 ease-brand hover:-translate-y-1 hover:border-line-2 hover:shadow-brand"
    >
      <span
        className={`mb-4 grid h-12 w-12 place-items-center rounded-2xl border border-line-2 bg-gradient-to-br ${ACCENTS[accent]}`}
      >
        <Icon size={24} />
      </span>
      <div className="text-3xl font-extrabold text-text font-en">
        {value === null ? <Skeleton className="h-8 w-12" /> : formatNumber(value, lang)}
      </div>
      <p className="mt-1 text-sm font-semibold text-muted">{t(labelKey)}</p>
    </Link>
  );
}

interface QuickAction {
  to: string;
  labelKey: MessageKey;
  icon: (props: { size?: number }) => JSX.Element;
}

const QUICK_ACTIONS: readonly QuickAction[] = [
  { to: '/link', labelKey: 'dash.qaLink', icon: LinkIcon },
  { to: '/managed', labelKey: 'dash.qaManaged', icon: ShieldIcon },
  { to: '/managers', labelKey: 'dash.qaRequests', icon: InboxIcon },
];

export function DashboardPage(): JSX.Element {
  const { t } = useI18n();
  const { user } = useAuth();
  const { incomingCount } = useRealtime();

  const managed = useAsyncData(() => api.managed(), []);
  const managers = useAsyncData(() => api.managers(), []);

  const greeting = user?.display_name?.trim() || user?.email?.split('@')[0] || '';

  return (
    <div className="animate-fade-in">
      <PageHeader title={`${t('dash.greeting')}، ${greeting}`} subtitle={t('dash.title')} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          labelKey="dash.statManaged"
          value={managed.data?.length ?? null}
          to="/managed"
          icon={ShieldIcon}
          accent="red"
        />
        <StatCard
          labelKey="dash.statManagers"
          value={managers.data?.length ?? null}
          to="/managers"
          icon={UsersIcon}
          accent="blue"
        />
        <StatCard
          labelKey="dash.statPending"
          value={incomingCount}
          to="/managers"
          icon={InboxIcon}
          accent="gold"
        />
      </div>

      <section className="mt-8">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-text">
          <DashboardIcon size={20} />
          {t('dash.quickActions')}
        </h2>
        <Card className="grid grid-cols-1 divide-line sm:grid-cols-3 sm:divide-x rtl:sm:divide-x-reverse">
          {QUICK_ACTIONS.map(({ to, labelKey, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-3 p-5 text-text transition-colors hover:bg-[var(--surface)]"
            >
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-[linear-gradient(135deg,rgba(46,158,79,.14),rgba(212,175,55,.14))] text-brand-red">
                <Icon size={20} />
              </span>
              <span className="font-semibold">{t(labelKey)}</span>
            </Link>
          ))}
        </Card>
      </section>
    </div>
  );
}
