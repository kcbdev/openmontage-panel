"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { RunState } from "./types";

const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL ||
  process.env.NEXT_PUBLIC_API_URL?.replace(/^http/, "ws") ||
  "ws://localhost:8000";

const MAX_RECONNECT_DELAY = 30000;
const INITIAL_RECONNECT_DELAY = 1000;
const HEARTBEAT_INTERVAL = 30000;

export interface WsMessage {
  type: "state_update" | "gate" | "checkpoint" | "anomaly" | "done";
  data: Record<string, unknown>;
}

export interface UseRunStreamResult {
  state: RunState | null;
  connected: boolean;
  lastEvent: WsMessage | null;
}

export function useRunStream(runId: string, token?: string | null): UseRunStreamResult {
  const [state, setState] = useState<RunState | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WsMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const delayRef = useRef(INITIAL_RECONNECT_DELAY);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const params = token ? `?token=${encodeURIComponent(token)}` : "";
    const ws = new WebSocket(`${WS_BASE}/runs/${runId}/stream${params}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      delayRef.current = INITIAL_RECONNECT_DELAY;
    };

    ws.onclose = () => {
      setConnected(false);
      const delay = delayRef.current;
      delayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY);
      reconnectTimer.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (e) => {
      try {
        const msg: WsMessage = JSON.parse(e.data);
        setLastEvent(msg);

        if (msg.type === "state_update") {
          setState(msg.data as unknown as RunState);
        } else if (msg.type === "anomaly") {
          setState((prev) =>
            prev
              ? {
                  ...prev,
                  status: "anomaly",
                  anomaly_reason: (msg.data.reason as string) || prev.anomaly_reason,
                }
              : null,
          );
        } else if (msg.type === "done") {
          setState((prev) => (prev ? { ...prev, status: "done" } : null));
        }
      } catch {
        /* skip malformed frames */
      }
    };
  }, [runId, token]);

  useEffect(() => {
    if (!runId) return;

    connect();

    heartbeatTimer.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, HEARTBEAT_INTERVAL);

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [runId, connect]);

  return { state, connected, lastEvent };
}
