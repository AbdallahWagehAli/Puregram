import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { STREAM_PATH } from '@/lib/api';
import type { ChatsEventData, CountEventData } from '@/types';

/**
 * A monotonically-increasing signal keyed by managed-user id. Detail views read
 * the value for their user id and re-fetch whenever it changes. A special key
 * SELF_KEY tracks the signed-in user's own whitelist changes.
 */
export const SELF_KEY = 'self';
export type ChatsSignals = Readonly<Record<string, number>>;

interface RealtimeValue {
  /** Count of pending incoming link requests (drives the topbar badge). */
  incomingCount: number;
  /** Count of link requests I sent that are still waiting on a handset. */
  outgoingCount: number;
  /** Number of accounts I supervise — rises the moment a handset approves. */
  linksCount: number;
  /** Count of pending unlink requests from accounts I supervise. */
  unlinkCount: number;
  /** Per-account version signals; bump triggers a re-fetch in open views. */
  chatsSignals: ChatsSignals;
  connected: boolean;
}

const RealtimeContext = createContext<RealtimeValue | null>(null);

const RECONNECT_DELAY_MS = 3000;

function parseEvent<T>(event: MessageEvent): T | null {
  try {
    return JSON.parse(event.data) as T;
  } catch {
    return null;
  }
}

/**
 * Subscribes to the backend SSE stream while the user is authenticated.
 * Reconnects automatically on error. `enabled` gates the connection so we do not
 * open a stream on the login/register screens.
 */
export function RealtimeProvider({
  enabled,
  children,
}: {
  enabled: boolean;
  children: ReactNode;
}): JSX.Element {
  const [incomingCount, setIncomingCount] = useState(0);
  const [outgoingCount, setOutgoingCount] = useState(0);
  const [linksCount, setLinksCount] = useState(0);
  const [unlinkCount, setUnlinkCount] = useState(0);
  const [chatsSignals, setChatsSignals] = useState<ChatsSignals>({});
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);
  const reconnectRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      setConnected(false);
      return;
    }

    let disposed = false;

    const bumpSignal = (key: string, version: number): void => {
      setChatsSignals((prev) => {
        // Use the server version as the signal value; ignore stale/equal versions.
        if ((prev[key] ?? -1) >= version) return prev;
        return { ...prev, [key]: version };
      });
    };

    const connect = (): void => {
      if (disposed) return;
      const source = new EventSource(STREAM_PATH, { withCredentials: true });
      sourceRef.current = source;

      source.onopen = () => {
        if (!disposed) setConnected(true);
      };

      const onCount = (name: string, apply: (count: number) => void): void => {
        source.addEventListener(name, (event) => {
          const data = parseEvent<CountEventData>(event as MessageEvent);
          if (data) apply(data.count);
        });
      };
      onCount('incoming', setIncomingCount);
      onCount('outgoing', setOutgoingCount);
      onCount('links', setLinksCount);
      onCount('unlink_request', setUnlinkCount);

      source.addEventListener('chats', (event) => {
        const data = parseEvent<ChatsEventData>(event as MessageEvent);
        if (!data) return;
        const key = data.self ? SELF_KEY : data.managed_user_id?.toString();
        if (key) bumpSignal(key, data.version);
      });

      // `ping` is a keep-alive heartbeat; no payload handling required.

      source.onerror = () => {
        if (disposed) return;
        setConnected(false);
        source.close();
        sourceRef.current = null;
        reconnectRef.current = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectRef.current !== null) window.clearTimeout(reconnectRef.current);
      sourceRef.current?.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [enabled]);

  const value = useMemo<RealtimeValue>(
    () => ({ incomingCount, outgoingCount, linksCount, unlinkCount, chatsSignals, connected }),
    [incomingCount, outgoingCount, linksCount, unlinkCount, chatsSignals, connected],
  );

  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtime(): RealtimeValue {
  const ctx = useContext(RealtimeContext);
  if (!ctx) throw new Error('useRealtime must be used within RealtimeProvider');
  return ctx;
}
