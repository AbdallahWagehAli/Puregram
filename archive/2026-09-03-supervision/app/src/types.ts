/**
 * API response types — mirror CONTROL_SPEC.md §4 exactly.
 * Timestamps are zero-padded ISO-8601 UTC strings (lexicographically sortable).
 */

export type Lang = 'ar' | 'en';
export type Theme = 'dark' | 'light';

/** Returned by the auth/me endpoints. */
export interface UserProfile {
  id: number;
  email: string;
  display_name: string | null;
  lang: Lang;
  tg_user_id: number | null;
  tg_verified: boolean;
  share_code: string | null;
}

/** Minimal user reference embedded in link requests. */
export interface UserRef {
  id: number;
  display_name: string | null;
  email: string | null;
  /** Set when the account is a supervised Telegram account (the usual case). */
  tg_user_id?: number | null;
  username?: string | null;
}

/** Pending request where I am the target (someone wants to manage me). */
export interface IncomingLinkRequest {
  id: number;
  requester: UserRef;
  created_at: string;
}

/**
 * Pending request where I am the requester (I want to supervise someone).
 *
 * `code` is the verification code the managed handset shows in its notification
 * — displayed here so both sides can see they match. It is NOT a credential:
 * approving requires the handset's own device token.
 */
export interface OutgoingLinkRequest {
  id: number;
  target: UserRef;
  code: string | null;
  expires_at: string | null;
  created_at: string;
}

/** Response of POST /links/requests. */
export interface LinkRequest {
  id: number;
  target: UserRef;
  code: string;
  expires_at: string;
}

/** An account I manage (GET /managed). */
export interface ManagedAccount {
  user_id: number;
  display_name: string | null;
  email: string | null;
  tg_user_id: number | null;
  username: string | null;
  tg_verified: boolean;
  known_count: number;
  allowed_count: number;
  last_seen_at: string | null;
}

/** A person who manages me (GET /managers). */
export interface Manager {
  user_id: number;
  display_name: string | null;
  email: string | null;
  since: string;
}

export type ChatKind = 'private' | 'group' | 'supergroup' | 'channel' | 'bot' | string;

/** A known Telegram chat with its effective allowed state. */
export interface Chat {
  chat_id: number;
  kind: ChatKind;
  title: string | null;
  username: string | null;
  allowed: boolean;
  last_seen_at: string | null;
}

/** GET /managed/:userId/chats. */
export interface ChatsResponse {
  tg_user_id: number | null;
  version: number;
  chats: Chat[];
}

/** PUT|DELETE /managed/:userId/chats/:chatId. */
export interface ChatToggleResponse {
  ok: true;
  allowed: boolean;
  version: number;
}

/** POST /managed/:userId/chats/bulk. */
export interface BulkAddResponse {
  ok: true;
  added: number;
  skipped: number;
  version: number;
}

export interface OkResponse {
  ok: true;
}

/** A pending unlink request from an account I supervise (GET /control/unlink-requests). */
export interface UnlinkRequest {
  id: number;
  managed_user_id: number;
  display_name: string | null;
  created_at: string;
}

/* ---- Server-Sent Events payloads (CONTROL_SPEC §4 "Real-time") ---- */

/** Payload of the counter events: incoming / outgoing / links / unlink_request. */
export interface CountEventData {
  count: number;
}

export interface ChatsEventData {
  managed_user_id?: number;
  self?: boolean;
  version: number;
}

