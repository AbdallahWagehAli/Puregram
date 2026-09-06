import { useI18n } from '@/context/I18nContext';
import { Toggle } from '@/components/Toggle';
import { Badge } from '@/components/ui';
import type { Chat } from '@/types';

const KIND_INITIAL: Record<string, string> = {
  private: 'P',
  group: 'G',
  supergroup: 'G',
  channel: 'C',
  bot: 'B',
};

function chatLabel(chat: Chat): string {
  return chat.title?.trim() || (chat.username ? `@${chat.username}` : `#${chat.chat_id}`);
}

/** One known chat with an allow/block switch. Disabled while a write is in flight. */
export function ChatRow({
  chat,
  pending,
  onToggle,
}: {
  chat: Chat;
  pending: boolean;
  onToggle: (chat: Chat, allowed: boolean) => void;
}): JSX.Element {
  const { t } = useI18n();
  const label = chatLabel(chat);

  return (
    <li className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-[var(--surface)]">
      <span
        className={`grid h-10 w-10 shrink-0 place-items-center rounded-full font-en text-sm font-bold ${
          chat.allowed ? 'bg-grad text-white' : 'bg-[var(--surface)] text-dim'
        }`}
        aria-hidden="true"
      >
        {KIND_INITIAL[chat.kind] ?? '#'}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold text-text">{label}</p>
        <div className="mt-0.5 flex items-center gap-2">
          <span className="font-en text-xs text-dim">{chat.kind}</span>
          {chat.username && (
            <span className="truncate font-en text-xs text-dim">@{chat.username}</span>
          )}
        </div>
      </div>
      <Badge tone={chat.allowed ? 'green' : 'neutral'}>
        {chat.allowed ? t('detail.toggleOn') : t('detail.toggleOff')}
      </Badge>
      <Toggle
        checked={chat.allowed}
        disabled={pending}
        onChange={(next) => onToggle(chat, next)}
        labelOn={`${label} — ${t('detail.toggleOn')}`}
        labelOff={`${label} — ${t('detail.toggleOff')}`}
      />
    </li>
  );
}
