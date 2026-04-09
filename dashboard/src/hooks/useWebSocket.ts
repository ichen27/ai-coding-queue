import { useEffect, useRef, useState, useCallback } from "react";
import type { ServerMessage, Command } from "../types";

const WS_URL = `ws://${window.location.host}/ws/dashboard`;
const RECONNECT_DELAY = 2000;

export function useWebSocket(onMessage: (msg: ServerMessage) => void) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let ws: WebSocket;

    function connect() {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data) as ServerMessage;
        onMessageRef.current(data);
      };
      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
      };
      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  const sendCommand = useCallback((cmd: Command) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  return { connected, sendCommand };
}
