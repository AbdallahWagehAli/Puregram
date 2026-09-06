import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useI18n } from '@/context/I18nContext';
import { useToast } from '@/context/ToastContext';
import { useRealtime } from '@/context/RealtimeContext';
import { api } from '@/lib/api';
import { useAsyncData } from '@/hooks/useAsyncData';
import { PageHeader } from '@/components/PageHeader';
import { Button, Card, Field, Spinner } from '@/components/ui';
import { CopyIcon, LinkIcon, SendIcon } from '@/components/icons';
import { errorMessage } from '@/lib/errors';
import { cleanString } from '@/lib/format';
import type { MessageKey } from '@/i18n/dictionary';
import type { OutgoingLinkRequest, UserRef } from '@/types';

const STEPS: readonly MessageKey[] = ['link.step1', 'link.step2', 'link.step3'];

/** Human label for the account a request targets: name, then @username, then id. */
function targetLabel(target: UserRef): string {
  const name = target.display_name?.trim();
  if (name) return name;
  if (target.username) return `@${target.username}`;
  if (target.tg_user_id) return String(target.tg_user_id);
  return target.email ?? '—';
}

/** Whole seconds left until `iso`, ticking every second; 0 once elapsed. */
function useCountdown(iso: string | null): number {
  const deadline = useMemo(() => (iso ? new Date(iso).getTime() : 0), [iso]);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!deadline) {
      setSeconds(0);
      return;
    }
    const tick = (): void =>
      setSeconds(Math.max(0, Math.round((deadline - Date.now()) / 1000)));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [deadline]);

  return seconds;
}

function formatClock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
}

/**
 * One request waiting on a handset: the verification code its notification
 * shows, a countdown to the deadline, and a cancel action.
 */
function PendingRequestCard({
  request,
  onCancelled,
}: {
  request: OutgoingLinkRequest;
  onCancelled: () => void;
}): JSX.Element {
  const { t, lang } = useI18n();
  const { notify } = useToast();
  const [busy, setBusy] = useState(false);
  const seconds = useCountdown(request.expires_at);

  const cancel = async (): Promise<void> => {
    setBusy(true);
    try {
      await api.cancelRequest(request.id);
      notify(t('link.cancelled'), 'success');
      onCancelled();
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    } finally {
      setBusy(false);
    }
  };

  const copyCode = async (): Promise<void> => {
    if (!request.code) return;
    try {
      await navigator.clipboard.writeText(request.code);
      notify(t('common.copied'), 'success');
    } catch {
      notify(t('common.error'), 'error');
    }
  };

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 font-bold text-text">
            <Spinner size={14} />
            {t('link.waiting')}
          </p>
          <p className="mt-1 text-sm text-muted">
            {t('link.waitingFor')}{' '}
            <span className="font-en font-bold text-text" dir="ltr">
              {targetLabel(request.target)}
            </span>
          </p>
        </div>
        <span
          className="rounded-full border border-line-2 px-3 py-1 font-en text-sm font-bold text-muted"
          dir="ltr"
        >
          {seconds > 0 ? formatClock(seconds) : t('link.expired')}
        </span>
      </div>

      <div className="mt-5 flex flex-col items-center gap-2 rounded-brand border border-line-2 bg-[var(--surface)] px-4 py-6">
        <span className="text-xs font-semibold uppercase tracking-wider text-dim">
          {t('link.codeLabel')}
        </span>
        <span
          className="font-en text-3xl font-black tracking-[0.2em] text-text sm:text-4xl"
          dir="ltr"
        >
          {request.code ?? '—'}
        </span>
        <button
          type="button"
          onClick={() => void copyCode()}
          className="mt-1 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-red transition-opacity hover:opacity-80"
        >
          <CopyIcon size={15} />
          {t('common.copy')}
        </button>
      </div>

      <p className="mt-4 text-sm text-muted">{t('link.waitingHint')}</p>

      <Button
        variant="line"
        size="sm"
        className="mt-4"
        loading={busy}
        onClick={() => void cancel()}
      >
        {t('link.cancelRequest')}
      </Button>
    </Card>
  );
}

/** Start supervision: identify the Telegram account, then wait for its handset. */
function SendRequestCard({ onSent }: { onSent: () => void }): JSX.Element {
  const { t, lang } = useI18n();
  const { notify } = useToast();

  const [target, setTarget] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    const value = cleanString(target);
    if (!value) {
      setError(t('err.required'));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.sendLinkRequest(value);
      notify(t('link.sent'), 'success');
      setTarget('');
      onSent();
    } catch (err) {
      setError(errorMessage(err, lang));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="p-6">
      <h2 className="mb-1 flex items-center gap-2 font-bold text-text">
        <SendIcon size={18} />
        {t('link.formTitle')}
      </h2>
      <p className="mb-4 text-sm text-muted">{t('link.formHint')}</p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        <Field
          label={t('link.field')}
          name="target"
          dir="ltr"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          placeholder={t('link.placeholder')}
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          error={error}
        />
        <Button type="submit" loading={submitting} className="self-start">
          <LinkIcon size={18} />
          {t('link.submit')}
        </Button>
      </form>
    </Card>
  );
}

export function LinkPage(): JSX.Element {
  const { t } = useI18n();
  const { notify } = useToast();
  const { outgoingCount, linksCount } = useRealtime();

  // The SSE counters change the moment a handset answers, so the pending list
  // re-fetches itself without the supervisor touching anything.
  const pending = useAsyncData(() => api.outgoingRequests(), [outgoingCount, linksCount]);
  const requests = pending.data ?? [];
  const pendingIds = requests.map((request) => request.id).join(',');

  // A request disappearing while the supervised-account count rises is an
  // approval; announce it instead of leaving the card to vanish silently.
  const [previous, setPrevious] = useState<{ ids: string; links: number } | null>(null);
  useEffect(() => {
    if (pending.loading) return;
    if (previous && previous.ids !== pendingIds && linksCount > previous.links) {
      notify(t('link.approved'), 'success');
    }
    setPrevious({ ids: pendingIds, links: linksCount });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingIds, pending.loading, linksCount]);

  return (
    <div className="animate-fade-in">
      <PageHeader title={t('link.title')} subtitle={t('link.subtitle')} />

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <div className="flex flex-col gap-6">
          <SendRequestCard onSent={pending.reload} />
          {requests.map((request) => (
            <PendingRequestCard key={request.id} request={request} onCancelled={pending.reload} />
          ))}
        </div>

        <Card className="p-6">
          <h2 className="mb-4 font-bold text-text">{t('link.howTitle')}</h2>
          <ol className="flex flex-col gap-4">
            {STEPS.map((step, index) => (
              <li key={step} className="flex items-start gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-grad font-en text-sm font-bold text-white">
                  {index + 1}
                </span>
                <p className="text-sm text-muted">{t(step)}</p>
              </li>
            ))}
          </ol>
          <p className="mt-5 rounded-brand border border-line-2 bg-[var(--surface)] p-4 text-sm text-muted">
            {t('link.note')}
          </p>
        </Card>
      </div>
    </div>
  );
}
