/**
 * Typed API client for the Puregram Control backend.
 *
 * - Base URL: VITE_API_BASE, falling back to '/control/v1' (same-origin in prod,
 *   Vite-proxied in dev — see vite.config.ts).
 * - Every request sends cookies (credentials: 'include').
 * - A 401 dispatches a global 'auth:unauthorized' event so the app can route to
 *   /login without coupling the client to the router.
 */

import type {
  BulkAddResponse,
  ChatToggleResponse,
  ChatsResponse,
  IncomingLinkRequest,
  Lang,
  LinkRequest,
  ManagedAccount,
  Manager,
  OkResponse,
  OutgoingLinkRequest,
  UnlinkRequest,
  UserProfile,
} from '@/types';

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/control/v1';

/** The path EventSource connects to (relative to origin, same-origin cookie). */
export const STREAM_PATH = `${API_BASE}/control/stream`;

export const UNAUTHORIZED_EVENT = 'auth:unauthorized';

/** Structured error carrying the HTTP status and the server's `detail` message. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  /** When true, a 401 will NOT emit the global unauthorized event (used by /me probe). */
  silentAuth?: boolean;
}

async function parseDetail(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === 'string') return detail;
      return JSON.stringify(detail);
    }
  } catch {
    // Body was not JSON — fall through to a generic message.
  }
  return response.statusText;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, silentAuth = false } = options;

  const init: RequestInit = {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (cause) {
    throw new ApiError(0, cause instanceof Error ? cause.message : 'Network error');
  }

  if (response.status === 401 && !silentAuth) {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseDetail(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/* ----------------------------- Auth & profile ----------------------------- */

export interface RegisterPayload {
  email: string;
  password: string;
  display_name?: string;
  lang?: Lang;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface ProfilePatch {
  display_name?: string;
  lang?: Lang;
}

export interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}

export const api = {
  register: (payload: RegisterPayload) =>
    request<UserProfile>('/control/register', { method: 'POST', body: payload }),

  login: (payload: LoginPayload) =>
    request<UserProfile>('/control/login', { method: 'POST', body: payload }),

  logout: () => request<OkResponse>('/control/logout', { method: 'POST' }),

  /** Probe the session without triggering a redirect on 401. */
  me: () => request<UserProfile>('/control/me', { silentAuth: true }),

  updateProfile: (patch: ProfilePatch) =>
    request<UserProfile>('/control/me', { method: 'PATCH', body: patch }),

  changePassword: (payload: PasswordChangePayload) =>
    request<OkResponse>('/control/account/password', { method: 'POST', body: payload }),

  /* ----------------------- Telegram account binding ----------------------- */

  bindTelegram: (tgUserId: number) =>
    request<UserProfile>('/control/me/telegram', { method: 'POST', body: { tg_user_id: tgUserId } }),

  unbindTelegram: () =>
    request<UserProfile>('/control/me/telegram', { method: 'DELETE' }),

  /* ------------------------------- Linking -------------------------------- */

  sendLinkRequest: (target: string) =>
    request<LinkRequest>('/control/links/requests', { method: 'POST', body: { target } }),

  incomingRequests: () =>
    request<IncomingLinkRequest[]>('/control/links/requests/incoming'),

  outgoingRequests: () =>
    request<OutgoingLinkRequest[]>('/control/links/requests/outgoing'),

  approveRequest: (id: number) =>
    request<OkResponse>(`/control/links/requests/${id}/approve`, { method: 'POST' }),

  declineRequest: (id: number) =>
    request<OkResponse>(`/control/links/requests/${id}/decline`, { method: 'POST' }),

  cancelRequest: (id: number) =>
    request<OkResponse>(`/control/links/requests/${id}/cancel`, { method: 'POST' }),

  /* ------------------------- Unlink requests (mgr) ------------------------ */

  listUnlinkRequests: () =>
    request<UnlinkRequest[]>('/control/unlink-requests'),

  approveUnlinkRequest: (id: number) =>
    request<OkResponse>(`/control/unlink-requests/${id}/approve`, { method: 'POST' }),

  denyUnlinkRequest: (id: number) =>
    request<OkResponse>(`/control/unlink-requests/${id}/deny`, { method: 'POST' }),

  /* --------------------------- Links overview ----------------------------- */

  managed: () => request<ManagedAccount[]>('/control/managed'),

  managers: () => request<Manager[]>('/control/managers'),

  unlinkManaged: (userId: number) =>
    request<OkResponse>(`/control/managed/${userId}`, { method: 'DELETE' }),

  removeManager: (userId: number) =>
    request<OkResponse>(`/control/managers/${userId}`, { method: 'DELETE' }),

  /* -------------------------------- Chats --------------------------------- */

  chats: (userId: number) =>
    request<ChatsResponse>(`/control/managed/${userId}/chats`),

  setChatAllowed: (userId: number, chatId: number, allowed: boolean) =>
    request<ChatToggleResponse>(`/control/managed/${userId}/chats/${chatId}`, {
      method: 'PUT',
      body: { allowed },
    }),

  /** Explicitly block a chat (survives the handset re-reporting it). */
  blockChat: (userId: number, chatId: number) =>
    request<ChatToggleResponse>(`/control/managed/${userId}/chats/${chatId}`, {
      method: 'DELETE',
    }),

  bulkAddChats: (userId: number, text: string) =>
    request<BulkAddResponse>(`/control/managed/${userId}/chats/bulk`, {
      method: 'POST',
      body: { text },
    }),
};
