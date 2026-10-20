"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/auth";
import {
  heartbeat,
  newestSnapshot,
  OPS_BASE,
  OperationsError,
  opsFetch,
  type Snapshot,
} from "@/lib/operations";

type State = {
  snapshot: Snapshot | null;
  error: string | null;
  connected: boolean;
  refresh: () => Promise<void>;
  mutate: <T>(path: string, body?: unknown) => Promise<T>;
  /** Case pages report what the analyst has open so teammates see it. */
  setCurrentCase: (caseId: string | null) => void;
};
const Context = createContext<State | null>(null);
export function OperationsProvider({ children }: { children: React.ReactNode }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const cursor = useRef(0);
  const inFlight = useRef<Promise<void> | null>(null);
  const currentCase = useRef<string | null>(null);
  const beat = useCallback(() => {
    if (document.visibilityState !== "visible") return;
    void heartbeat(currentCase.current).catch(() => {});
  }, []);
  const setCurrentCase = useCallback(
    (caseId: string | null) => {
      currentCase.current = caseId;
      beat();
    },
    [beat],
  );
  useEffect(() => {
    beat();
    const timer = setInterval(beat, 15000);
    document.addEventListener("visibilitychange", beat);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", beat);
    };
  }, [beat]);
  const refresh = useCallback(() => {
    if (inFlight.current) return inFlight.current;
    const request = opsFetch<Snapshot>("/snapshot")
      .then((data) => {
        cursor.current = Math.max(cursor.current, data.cursor);
        setSnapshot((current) => newestSnapshot(current, data));
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Operations service unavailable.");
        throw err;
      })
      .finally(() => {
        inFlight.current = null;
      });
    inFlight.current = request;
    return request;
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let stopped = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    void refresh().catch(() => {});
    const polling = setInterval(() => {
      void refresh().catch(() => {});
    }, 10000);
    const reconnect = () => {
      if (!stopped)
        reconnectTimer = setTimeout(() => {
          void stream();
        }, 3000);
    };
    async function stream() {
      try {
        const token = getToken();
        if (!token) throw new OperationsError(401, "Sign in to open operations.");
        const response = await fetch(`${OPS_BASE}/events?after=${cursor.current}`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok || !response.body)
          throw new Error("Live connection unavailable. Retrying; the last snapshot remains visible.");
        setConnected(true);
        await refresh();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!stopped) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true }).replaceAll("\r\n", "\n");
          let boundary: number;
          while ((boundary = buffer.indexOf("\n\n")) >= 0) {
            const event = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            if (event.split("\n").some((line) => line.startsWith("data:"))) await refresh();
          }
        }
      } catch (err) {
        if (!stopped) setError(err instanceof Error ? err.message : "Live connection interrupted.");
      } finally {
        if (!stopped) {
          setConnected(false);
          reconnect();
        }
      }
    }
    void stream();
    const recover = () => {
      void refresh().catch(() => {});
    };
    window.addEventListener("online", recover);
    window.addEventListener("focus", recover);
    return () => {
      stopped = true;
      controller.abort();
      clearInterval(polling);
      clearTimeout(reconnectTimer);
      window.removeEventListener("online", recover);
      window.removeEventListener("focus", recover);
    };
  }, [refresh]);
  const mutate = useCallback(
    async <T,>(path: string, body?: unknown): Promise<T> => {
      const result = await opsFetch<T>(path, {
        method: "POST",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      await inFlight.current?.catch(() => {});
      await refresh();
      return result;
    },
    [refresh],
  );
  return (
    <Context.Provider value={{ snapshot, error, connected, refresh, mutate, setCurrentCase }}>
      {children}
    </Context.Provider>
  );
}
export function useOperations() {
  const value = useContext(Context);
  if (!value) throw new Error("Operations provider missing");
  return value;
}
