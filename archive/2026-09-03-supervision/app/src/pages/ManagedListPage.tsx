import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '@/context/I18nContext';
import { useToast } from '@/context/ToastContext';
import { useRealtime } from '@/context/RealtimeContext';
import { api } from '@/lib/api';
import { useAsyncData } from '@/hooks/useAsyncData';
import { PageHeader } from '@/components/PageHeader';
import { Button, Badge, Card, EmptyState, ErrorState } from '@/components/ui';
import { SkeletonList } from '@/components/Skeleton';
import { CheckIcon, ChevronIcon, LinkIcon, XIcon } from '@/components/icons';
import { errorMessage } from '@/lib/errors';
import { accountHandle, accountInitial, accountName, formatDateTime, formatNumber } from '@/lib/format';
import type { ManagedAccount, UnlinkRequest } from '@/types';

function AccountCard({ account }: { account: ManagedAccount }): JSX.Element {
  const { t, lang } = useI18n();
  const name = accountName(account);
  const handle = accountHandle(account);
  const initial = accountInitial(account);

  return (
    <Link
      to={`/managed/${account.user_id}`}
      className="group flex items-center gap-4 rounded-brand-lg border border-line bg-bg-2 p-4 transition-all duration-200 ease-brand hover:-translate-y-0.5 hover:border-line-2 hover:shadow-brand"
    >
      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-grad font-en text-lg font-bold text-white">
        {initial}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate font-bold text-text">{name}</p>
          {account.tg_verified && <Badge tone="gold">{t('settings.tgVerified')}</Badge>}
        </div>
        {handle && <p className="truncate font-en text-xs text-dim" dir="ltr">{handle}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          {account.tg_user_id === null ? (
            <Badge tone="red">{t('managed.notBound')}</Badge>
          ) : (
            <>
              <Badge tone="green">
                {formatNumber(account.allowed_count, lang)} {t('managed.allowed')}
              </Badge>
              <Badge>
                {formatNumber(account.known_count, lang)} {t('managed.known')}
              </Badge>
            </>
          )}
        </div>
      </div>
      <span className="hidden text-dim transition-colors group-hover:text-brand-red sm:block">
        <ChevronIcon size={20} className="rtl:rotate-180" />
      </span>
    </Link>
  );
}

function unlinkName(req: UnlinkRequest): string {
  return req.display_name?.trim() || `#${req.managed_user_id}`;
}

/**
 * Pending unlink requests from accounts I supervise. Approving revokes the link;
 * denying keeps it. Refetches whenever the SSE `unlink_request` count changes.
 */
function UnlinkRequests(): JSX.Element | null {
  const { t, lang } = useI18n();
  const { notify } = useToast();
  const { unlinkCount } = useRealtime();
  const { data, error, reload } = useAsyncData(() => api.listUnlinkRequests(), [unlinkCount]);
  const [busyId, setBusyId] = useState<number | null>(null);

  const act = async (id: number, action: 'approve' | 'deny'): Promise<void> => {
    setBusyId(id);
    try {
      if (action === 'approve') await api.approveUnlinkRequest(id);
      else await api.denyUnlinkRequest(id);
      notify(action === 'approve' ? t('unlink.approved') : t('unlink.denied'), 'success');
      reload();
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    } finally {
      setBusyId(null);
    }
  };

  const items = data ?? [];
  // Hide the section entirely when there is nothing to act on (and no error).
  if (!error && items.length === 0) return null;

  return (
    <section>
      <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-text">
        <LinkIcon size={20} />
        {t('unlink.title')}
      </h2>
      {error ? (
        <ErrorState message={errorMessage(error, lang)} onRetry={reload} />
      ) : (
        <div className="grid gap-3">
          {items.map((req) => (
            <Card key={req.id} className="flex flex-wrap items-center gap-3 p-4">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-grad font-en text-sm font-bold text-white">
                {unlinkName(req).charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold text-text">{unlinkName(req)}</p>
                <p className="truncate text-xs text-muted">{t('unlink.hint')}</p>
                <p className="truncate font-en text-xs text-dim">
                  {t('unlink.requested')} {formatDateTime(req.created_at, lang)}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="danger"
                  loading={busyId === req.id}
                  onClick={() => act(req.id, 'approve')}
                >
                  <CheckIcon size={16} />
                  {t('action.approve')}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busyId === req.id}
                  onClick={() => act(req.id, 'deny')}
                >
                  <XIcon size={16} />
                  {t('action.deny')}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

export function ManagedListPage(): JSX.Element {
  const { t, lang } = useI18n();
  const { data, loading, error, reload } = useAsyncData(() => api.managed(), []);

  return (
    <div className="animate-fade-in">
      <PageHeader title={t('managed.title')} subtitle={t('managed.subtitle')} />

      <div className="flex flex-col gap-8">
        <UnlinkRequests />

        <section>
          {loading && <SkeletonList count={3} />}

          {!loading && error && <ErrorState message={errorMessage(error, lang)} onRetry={reload} />}

          {!loading && !error && data && data.length === 0 && (
            <EmptyState
              title={t('managed.empty')}
              hint={t('managed.emptyCta')}
              action={
                <Link to="/link">
                  <Button size="sm">{t('dash.qaLink')}</Button>
                </Link>
              }
            />
          )}

          {!loading && !error && data && data.length > 0 && (
            <div className="grid gap-3">
              {data.map((account) => (
                <div key={account.user_id}>
                  <AccountCard account={account} />
                  <span className="sr-only">
                    {t('managed.lastSeen')}: {formatDateTime(account.last_seen_at, lang)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
