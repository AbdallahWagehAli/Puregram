import type { Lang } from '@/types';

const LOCALE: Record<Lang, string> = { ar: 'ar-EG', en: 'en-US' };

/** Format an ISO-8601 UTC timestamp into a localized date+time, or em-dash. */
export function formatDateTime(iso: string | null, lang: Lang): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(LOCALE[lang], {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

/** Localized integer (Arabic-Indic digits in Arabic). */
export function formatNumber(value: number, lang: Lang): string {
  return new Intl.NumberFormat(LOCALE[lang]).format(value);
}

/** Trim and collapse a user-entered string; returns null when empty. */
export function cleanString(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/** Anything the panel renders as a person: a supervised Telegram account (no
 *  email) or a web account (no Telegram identity). */
export interface AccountLike {
  display_name?: string | null;
  username?: string | null;
  tg_user_id?: number | null;
  email?: string | null;
}

/**
 * The headline name for an account. Supervised accounts are passwordless and
 * have no email, so the fallback chain runs name → @username → numeric id →
 * email, and only then to a dash.
 */
export function accountName(account: AccountLike): string {
  const name = account.display_name?.trim();
  if (name) return name;
  if (account.username) return `@${account.username}`;
  if (account.tg_user_id) return String(account.tg_user_id);
  return account.email?.trim() || '—';
}

/** The secondary line under the name; empty when it would repeat the name. */
export function accountHandle(account: AccountLike): string {
  const name = account.display_name?.trim();
  if (account.username) return name ? `@${account.username}` : '';
  if (account.email) return name || account.email !== name ? account.email : '';
  return account.tg_user_id && name ? String(account.tg_user_id) : '';
}

/** First letter for an avatar bubble, skipping the '@' of a username. */
export function accountInitial(account: AccountLike): string {
  const label = accountName(account).replace(/^@/, '');
  return label.charAt(0).toUpperCase() || '?';
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim());
}
