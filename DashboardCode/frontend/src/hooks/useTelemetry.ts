import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { BackendHealth, ConnectionState, DataHealth, EngineTelemetry } from '../types/telemetry';
import { monitoringThresholds } from '../config/thresholds';

const HISTORY_LIMIT = 1200;
const FLUSH_MS = 120;

export function useTelemetry() {
  const [telemetry, setTelemetry] = useState<EngineTelemetry | null>(null);
  const [history, setHistory] = useState<EngineTelemetry[]>([]);
  const [dataHealth, setDataHealth] = useState<DataHealth | null>(null);
  const [backendHealth, setBackendHealth] = useState<BackendHealth | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>('DISCONNECTED');
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const latestRef = useRef<EngineTelemetry | null>(null);
  const pendingRef = useRef<EngineTelemetry | null>(null);
  const flushTimerRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const fetchBootstrap = useCallback(async () => {
    const API_BASE = import.meta.env.VITE_API_URL || '';
    try {
      const [latestResponse, healthResponse, dataHealthResponse] = await Promise.all([
        fetch(`${API_BASE}/api/telemetry/latest`),
        fetch(`${API_BASE}/api/health`),
        fetch(`${API_BASE}/api/data-health`),
      ]);

      if (latestResponse.ok) {
        const latest = (await latestResponse.json()) as EngineTelemetry;
        if (latest.timestamp && latest.sequence > 0) {
          latestRef.current = latest;
          setTelemetry(latest);
          setHistory([latest]);
          setLastUpdate(latest.timestamp);
        }
      }
      if (healthResponse.ok) {
        setBackendHealth((await healthResponse.json()) as BackendHealth);
      }
      if (dataHealthResponse.ok) {
        setDataHealth((await dataHealthResponse.json()) as DataHealth);
      }
    } catch {
      // Bootstrap is best-effort; the websocket will retry.
    }
  }, []);

  const flushPending = useCallback(() => {
    flushTimerRef.current = null;
    if (!pendingRef.current) {
      return;
    }

    const next = pendingRef.current;
    pendingRef.current = null;
    latestRef.current = next;
    setTelemetry(next);
    setLastUpdate(next.timestamp);
    setHistory((current) => {
      const appended = [...current, next];
      return appended.slice(-HISTORY_LIMIT);
    });
  }, []);

  const scheduleFlush = useCallback(() => {
    if (flushTimerRef.current !== null) {
      return;
    }
    flushTimerRef.current = window.setTimeout(flushPending, FLUSH_MS);
  }, [flushPending]);

  const connect = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      return;
    }

    const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/telemetry';
    const socket = new WebSocket(WS_BASE);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnectionState('LIVE');
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const next = payload.telemetry as EngineTelemetry;
        if (next) {
          pendingRef.current = next;
          scheduleFlush();
        }
      } catch {
        // Ignore malformed payloads but keep the connection alive.
      }
    };

    socket.onclose = () => {
      setConnectionState('DISCONNECTED');
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      reconnectTimerRef.current = window.setTimeout(connect, 1500);
    };

    socket.onerror = () => {
      setConnectionState('DISCONNECTED');
    };
  }, [scheduleFlush]);

  useEffect(() => {
    void fetchBootstrap();
    connect();

    const pollDataHealth = window.setInterval(async () => {
      const API_BASE = import.meta.env.VITE_API_URL || '';
      try {
      const [healthResponse, dataHealthResponse] = await Promise.all([
          fetch(`${API_BASE}/api/health`),
          fetch(`${API_BASE}/api/data-health`),
        ]);
        if (healthResponse.ok) {
          setBackendHealth((await healthResponse.json()) as BackendHealth);
        }
        if (dataHealthResponse.ok) {
          setDataHealth((await dataHealthResponse.json()) as DataHealth);
        }
      } catch {
        // Leave previous health state in place.
      }
    }, 1000);

    return () => {
      window.clearInterval(pollDataHealth);
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (flushTimerRef.current !== null) {
        window.clearTimeout(flushTimerRef.current);
      }
    };
  }, [connect, fetchBootstrap]);

  const freshness = useMemo(() => {
    if (!dataHealth) {
      return { freshSignals: 0, totalSignals: 12 };
    }
    return {
      freshSignals: dataHealth.signals_fresh,
      totalSignals: dataHealth.signals_total,
    };
  }, [dataHealth]);

  const stale = useMemo(() => {
    if (!lastUpdate) {
      return true;
    }
    return Date.now() - new Date(lastUpdate).getTime() > monitoringThresholds.freshnessStaleMs;
  }, [lastUpdate]);

  return {
    telemetry,
    history,
    dataHealth,
    backendHealth,
    connectionState,
    lastUpdate,
    stale,
    freshness,
  };
}
