import { useState } from 'react';
import { useI18n } from '@/context/I18nContext';
import { useToast } from '@/context/ToastContext';
import { useRealtime } from '@/context/RealtimeContext';
import { api } from '@/lib/api';
import { useAsyncData } from '@/hooks/useAsyncData';
import { PageHeader } from '@/components/PageHeader';
import { Button, Badge, Card, EmptyState, ErrorState } from '@/components/ui';
import { SkeletonList } from '@/components/Skeleton';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { CheckIcon, InboxIcon, SendIcon, UsersIcon, XIcon } from '@/components/icons';
import { errorMessage } from '@/lib/errors';
import { accountHandle, accountName, formatDateTime } from '@/lib/format';
import type { IncomingLinkRequest, Manager, OutgoingLinkRequest, UserRef } from '@/types';

function personName(ref: UserRef): string {
  return accountName(ref);
}

function Avatar({ label }: { label: string }): JSX.Element {
  return (
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-grad font-en text-sm font-bold text-white">
      {label.charAt(0).toUpperCase()}
    </span>
  );
}

function SectionTitle({
  icon: Icon,
  title,
}: {
  icon: (p: { size?: number }) => JSX.Element;
  title: string;
}): JSX.Element {
  return (
    <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-text">
      <Icon size={20} />
      {title}
    </h2>
  );
}

/** Incoming link requests (people asking to manage me): approve / decline. */
function IncomingRequests({
  items,
  onChanged,
}: {
  items: IncomingLinkRequest[];
  onChanged: () => void;
}): JSX.Element {
  const { t, lang } = useI18n();
  const { notify } = useToast();
  const [busyId, setBusyId] = useState<number | null>(null);

  const act = async (id: number, action: 'approve' | 'decline'): Promise<void> => {
    setBusyId(id);
    try {
      if (action === 'approve') await api.approveRequest(id);
      else await api.declineRequest(id);
      notify(t('settings.saved'), 'success');
      onChanged();
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section>
      <SectionTitle icon={InboxIcon} title={t('managers.incoming')} />
      {items.length === 0 ? (
        <EmptyState title={t('managers.incomingEmpty')} />
      ) : (
        <div className="grid gap-3">
          {items.map((req) => (
            <Card key={req.id} className="flex flex-wrap items-center gap-3 p-4">
              <Avatar label={personName(req.requester)} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold text-text">{personName(req.requester)}</p>
                <p className="truncate font-en text-xs text-dim">{req.requester.email}</p>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
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
                  onClick={() => act(req.id, 'decline')}
                >
                  <XIcon size={16} />
                  {t('action.decline')}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

/** Outgoing link requests (I asked to manage someone): cancel. */
function OutgoingRequests({
  items,
  onChanged,
}: {
  items: OutgoingLinkRequest[];
  onChanged: () => void;
}): JSX.Element {
  const { t, lang } = useI18n();
  const { notify } = useToast();
  const [busyId, setBusyId] = useState<number | null>(null);

  const cancel = async (id: number): Promise<void> => {
    setBusyId(id);
    try {
      await api.cancelRequest(id);
      onChanged();
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section>
      <SectionTitle icon={SendIcon} title={t('managers.outgoing')} />
      {items.length === 0 ? (
        <EmptyState title={t('managers.outgoingEmpty')} />
      ) : (
        <div className="grid gap-3">
          {items.map((req) => (
            <Card key={req.id} className="flex flex-wrap items-center gap-3 p-4">
              <Avatar label={personName(req.target)} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold text-text">{personName(req.target)}</p>
                <p className="truncate font-en text-xs text-dim">{req.target.email}</p>
              </div>
              <Badge tone="gold">{t('managers.outgoingHint')}</Badge>
              <Button
                size="sm"
                variant="ghost"
                loading={busyId === req.id}
                onClick={() => cancel(req.id)}
              >
                {t('action.cancel')}
              </Button>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

/** Active managers over me: remove. */
function ManagerList({
  items,
  onChanged,
}: {
  items: Manager[];
  onChanged: () => void;
}): JSX.Element {
  const { t, lang } = useI18n();
  const { notify } = useToast();
  const [target, setTarget] = useState<Manager | null>(null);
  const [busy, setBusy] = useState(false);

  const remove = async (): Promise<void> => {
    if (!target) return;
    setBusy(true);
    try {
      await api.removeManager(target.user_id);
      notify(t('settings.saved'), 'success');
      onChanged();
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    } finally {
      setBusy(false);
      setTarget(null);
    }
  };

  return (
    <section>
      <SectionTitle icon={UsersIcon} title={t('managers.title')} />
      {items.length === 0 ? (
        <EmptyState title={t('managers.empty')} />
      ) : (
        <div className="grid gap-3">
          {items.map((manager) => {
            const name = accountName(manager);
            const handle = accountHandle(manager);
            return (
              <Card key={manager.user_id} className="flex flex-wrap items-center gap-3 p-4">
                <Avatar label={name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold text-text">{name}</p>
                  {handle && (
                    <p className="truncate font-en text-xs text-dim" dir="ltr">{handle}</p>
                  )}
                </div>
                <span className="text-xs text-dim">
                  {t('managers.since')} {formatDateTime(manager.since, lang)}
                </span>
                <Button size="sm" variant="danger" onClick={() => setTarget(manager)}>
                  {t('action.remove')}
                </Button>
              </Card>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        open={target !== null}
        message={t('managers.removeConfirm')}
        confirmLabel={t('action.remove')}
        busy={busy}
        onConfirm={remove}
        onCancel={() => setTarget(null)}
      />
    </section>
  );
}

export function ManagersPage(): JSX.Element {
  const { t, lang } = useI18n();
  const { incomingCount } = useRealtime();

  // The incoming SSE count drives re-fetch of all three lists when it changes.
  const managers = useAsyncData(() => api.managers(), [incomingCount]);
  const incoming = useAsyncData(() => api.incomingRequests(), [incomingCount]);
  const outgoing = useAsyncData(() => api.outgoingRequests(), [incomingCount]);

  const loading = managers.loading || incoming.loading || outgoing.loading;
  const firstError = managers.error ?? incoming.error ?? outgoing.error;

  const reloadAll = (): void => {
    managers.reload();
    incoming.reload();
    outgoing.reload();
  };

  return (
    <div className="animate-fade-in">
      <PageHeader title={t('managers.title')} subtitle={t('managers.subtitle')} />

      {loading && <SkeletonList count={4} />}

      {!loading && firstError && (
        <ErrorState message={errorMessage(firstError, lang)} onRetry={reloadAll} />
      )}

      {!loading && !firstError && (
        <div className="flex flex-col gap-8">
          <IncomingRequests items={incoming.data ?? []} onChanged={reloadAll} />
          <ManagerList items={managers.data ?? []} onChanged={reloadAll} />
          <OutgoingRequests items={outgoing.data ?? []} onChanged={reloadAll} />
        </div>
      )}
    </div>
  );
}
