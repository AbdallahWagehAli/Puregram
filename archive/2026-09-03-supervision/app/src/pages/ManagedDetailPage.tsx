import { useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useI18n } from '@/context/I18nContext';
import { useToast } from '@/context/ToastContext';
import { useRealtime } from '@/context/RealtimeContext';
import { api } from '@/lib/api';
import { useManagedChats } from '@/hooks/useManagedChats';
import { PageHeader } from '@/components/PageHeader';
import { Button, Badge, Card, EmptyState, ErrorState } from '@/components/ui';
import { Skeleton } from '@/components/Skeleton';
import { ChatRow } from '@/components/ChatRow';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { ChevronIcon, PlusIcon } from '@/components/icons';
import { errorMessage } from '@/lib/errors';
import { formatNumber } from '@/lib/format';
import type { MessageKey } from '@/i18n/dictionary';
import type { Chat } from '@/types';

function NotFound(): JSX.Element {
  const { t } = useI18n();
  return (
    <EmptyState
      title={t('err.notFound')}
      action={
        <Link to="/managed">
          <Button size="sm" variant="line">
            {t('action.back')}
          </Button>
        </Link>
      }
    />
  );
}

function BulkAddForm({
  onAdd,
}: {
  onAdd: (text: string) => Promise<{ added: number; skipped: number }>;
}): JSX.Element {
  const { t, lang } = useI18n();
  const { notify } = useToast();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      const { added, skipped } = await onAdd(trimmed);
      notify(`${t('detail.bulkResult')}: ${added} · ${t('detail.bulkSkipped')}: ${skipped}`, 'success');
      setText('');
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <h2 className="mb-3 flex items-center gap-2 font-bold text-text">
        <PlusIcon size={18} />
        {t('detail.bulkTitle')}
      </h2>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t('detail.bulkPlaceholder')}
          rows={3}
          dir="ltr"
          className="w-full resize-y rounded-xl border border-line-2 bg-[var(--surface)] px-4 py-3 font-en text-sm text-text outline-none transition-colors placeholder:text-dim focus:border-brand-red"
        />
        <Button type="submit" size="sm" loading={busy} disabled={!text.trim()} className="self-end">
          {t('action.add')}
        </Button>
      </form>
    </Card>
  );
}

type ChatFilter = 'all' | 'allowed' | 'blocked';

const FILTERS: ReadonlyArray<{ value: ChatFilter; label: MessageKey }> = [
  { value: 'all', label: 'detail.filterAll' },
  { value: 'allowed', label: 'detail.filterAllowed' },
  { value: 'blocked', label: 'detail.filterBlocked' },
];

/** Search box + allowed/blocked filter — a real account has hundreds of chats. */
function ChatFilterBar({
  query,
  filter,
  onQuery,
  onFilter,
}: {
  query: string;
  filter: ChatFilter;
  onQuery: (value: string) => void;
  onFilter: (value: ChatFilter) => void;
}): JSX.Element {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <input
        type="search"
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        placeholder={t('detail.search')}
        aria-label={t('common.search')}
        className="w-full rounded-xl border border-line-2 bg-[var(--surface)] px-4 py-2.5 text-text outline-none transition-colors placeholder:text-dim focus:border-brand-red"
      />
      <div className="flex shrink-0 gap-1 rounded-xl border border-line-2 bg-[var(--surface)] p-1">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onFilter(option.value)}
            aria-pressed={filter === option.value}
            className={`rounded-lg px-3 py-1.5 text-sm font-bold transition-colors ${
              filter === option.value ? 'bg-grad text-white' : 'text-muted hover:text-text'
            }`}
          >
            {t(option.label)}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Case-insensitive match over the title, @username and numeric id. */
function matchesQuery(chat: Chat, needle: string): boolean {
  if (!needle) return true;
  const haystack = [chat.title, chat.username, String(chat.chat_id)]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(needle);
}

export function ManagedDetailPage(): JSX.Element {
  const { userId: userIdParam } = useParams();
  const userId = Number(userIdParam);
  const { t, lang } = useI18n();
  const { notify } = useToast();
  const { connected } = useRealtime();
  const navigate = useNavigate();

  const [confirmUnlink, setConfirmUnlink] = useState(false);
  const [unlinking, setUnlinking] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<ChatFilter>('all');

  const { data, loading, error, pending, reload, toggleChat, bulkAdd } = useManagedChats(userId);

  const allowedCount = useMemo(
    () => data?.chats.filter((c) => c.allowed).length ?? 0,
    [data],
  );

  const visibleChats = useMemo(() => {
    const needle = query.trim().toLowerCase().replace(/^@/, '');
    return (data?.chats ?? []).filter(
      (chat) =>
        matchesQuery(chat, needle) &&
        (filter === 'all' || (filter === 'allowed') === chat.allowed),
    );
  }, [data, query, filter]);

  if (!Number.isInteger(userId) || userId <= 0) return <NotFound />;

  const handleToggle = async (chat: Chat, allowed: boolean): Promise<void> => {
    try {
      await toggleChat(chat, allowed);
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
    }
  };

  const handleUnlink = async (): Promise<void> => {
    setUnlinking(true);
    try {
      await api.unlinkManaged(userId);
      notify(t('detail.unlinkTitle'), 'success');
      navigate('/managed', { replace: true });
    } catch (err) {
      notify(errorMessage(err, lang), 'error');
      setUnlinking(false);
      setConfirmUnlink(false);
    }
  };

  const isBound = data !== null && data.tg_user_id !== null;

  return (
    <div className="animate-fade-in">
      <Link
        to="/managed"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-muted transition-colors hover:text-brand-red"
      >
        <ChevronIcon size={16} className="ltr:rotate-180" />
        {t('action.back')}
      </Link>

      <PageHeader
        title={t('detail.title')}
        subtitle={
          isBound
            ? `${formatNumber(allowedCount, lang)} / ${formatNumber(data.chats.length, lang)} ${t('detail.allowedOf')}`
            : undefined
        }
        action={
          <div className="flex items-center gap-2">
            {connected && <Badge tone="green">● {t('detail.liveOn')}</Badge>}
            {data && (
              <Badge tone="gold">
                {t('detail.version')}: {formatNumber(data.version, lang)}
              </Badge>
            )}
          </div>
        }
      />

      {loading && (
        <div className="grid gap-3">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}

      {!loading && error && <ErrorState message={errorMessage(error, lang)} onRetry={reload} />}

      {!loading && !error && data && !isBound && (
        <EmptyState title={t('detail.notBoundTitle')} hint={t('detail.notBoundHint')} />
      )}

      {!loading && !error && data && isBound && (
        <div className="flex flex-col gap-6">
          {data.chats.length === 0 ? (
            <EmptyState title={t('detail.noChats')} hint={t('detail.noChatsHint')} />
          ) : (
            <>
              <ChatFilterBar
                query={query}
                filter={filter}
                onQuery={setQuery}
                onFilter={setFilter}
              />
              {visibleChats.length === 0 ? (
                <EmptyState title={t('detail.noMatches')} />
              ) : (
                <Card className="overflow-hidden">
                  <ul className="divide-y divide-line">
                    {visibleChats.map((chat) => (
                      <ChatRow
                        key={chat.chat_id}
                        chat={chat}
                        pending={pending.has(chat.chat_id)}
                        onToggle={handleToggle}
                      />
                    ))}
                  </ul>
                </Card>
              )}
            </>
          )}

          <BulkAddForm onAdd={bulkAdd} />

          <div className="flex justify-end">
            <Button variant="danger" size="sm" onClick={() => setConfirmUnlink(true)}>
              {t('detail.unlinkTitle')}
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmUnlink}
        message={t('detail.unlinkConfirm')}
        confirmLabel={t('action.unlink')}
        busy={unlinking}
        onConfirm={handleUnlink}
        onCancel={() => setConfirmUnlink(false)}
      />
    </div>
  );
}
