import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '@/lib/api';
import { useRealtime } from '@/context/RealtimeContext';
import type { Chat, ChatsResponse } from '@/types';

interface ManagedChatsState {
  data: ChatsResponse | null;
  loading: boolean;
  error: ApiError | null;
  /** chat_ids with an in-flight write. */
  pending: ReadonlySet<number>;
  reload: () => void;
  toggleChat: (chat: Chat, allowed: boolean) => Promise<void>;
  bulkAdd: (text: string) => Promise<{ added: number; skipped: number }>;
}

/**
 * Loads and mutates the whitelist for one managed account.
 *
 * - Toggles are optimistic: the UI flips immediately, then the response (carrying
 *   the authoritative `allowed`) reconciles the row. On failure the row reverts.
 * - The SSE `chats` signal for this user id triggers a background re-fetch so the
 *   view stays live when another manager or device changes the list.
 */
export function useManagedChats(userId: number): ManagedChatsState {
  const [data, setData] = useState<ChatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState<ReadonlySet<number>>(new Set());
  const [nonce, setNonce] = useState(0);

  const { chatsSignals } = useRealtime();
  const signal = chatsSignals[userId.toString()];
  // Track the last version we have rendered to ignore our own version bumps.
  const renderedVersion = useRef<number>(-1);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  const toApiError = (err: unknown): ApiError =>
    err instanceof ApiError ? err : new ApiError(0, 'Unknown error');

  // Initial load + explicit reloads.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void api
      .chats(userId)
      .then((response) => {
        if (cancelled) return;
        setData(response);
        renderedVersion.current = response.version;
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(toApiError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [userId, nonce]);

  // Live re-fetch when the server reports a newer version than we rendered.
  useEffect(() => {
    if (signal === undefined) return;
    if (signal <= renderedVersion.current) return;
    let cancelled = false;
    void api
      .chats(userId)
      .then((response) => {
        if (cancelled) return;
        setData(response);
        renderedVersion.current = response.version;
      })
      .catch(() => {
        /* a transient refetch failure keeps the last good state */
      });
    return () => {
      cancelled = true;
    };
  }, [signal, userId]);

  const setChatAllowed = useCallback((chatId: number, allowed: boolean) => {
    setData((prev) =>
      prev
        ? {
            ...prev,
            chats: prev.chats.map((c) => (c.chat_id === chatId ? { ...c, allowed } : c)),
          }
        : prev,
    );
  }, []);

  const markPending = useCallback((chatId: number, on: boolean) => {
    setPending((prev) => {
      const next = new Set(prev);
      if (on) next.add(chatId);
      else next.delete(chatId);
      return next;
    });
  }, []);

  const toggleChat = useCallback(
    async (chat: Chat, allowed: boolean) => {
      const previous = chat.allowed;
      setChatAllowed(chat.chat_id, allowed); // optimistic
      markPending(chat.chat_id, true);
      try {
        const result = await api.setChatAllowed(userId, chat.chat_id, allowed);
        setChatAllowed(chat.chat_id, result.allowed); // reconcile to server truth
        // Our own write bumps the version; record it so SSE does not double-fetch.
        setData((prev) => {
          if (prev) renderedVersion.current = prev.version + 1;
          return prev ? { ...prev, version: prev.version + 1 } : prev;
        });
      } catch (err) {
        setChatAllowed(chat.chat_id, previous); // revert
        throw toApiError(err);
      } finally {
        markPending(chat.chat_id, false);
      }
    },
    [userId, setChatAllowed, markPending],
  );

  const bulkAdd = useCallback(
    async (text: string) => {
      const result = await api.bulkAddChats(userId, text);
      reload();
      return { added: result.added, skipped: result.skipped };
    },
    [userId, reload],
  );

  return { data, loading, error, pending, reload, toggleChat, bulkAdd };
}
