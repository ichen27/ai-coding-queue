import { useCallback, useState } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { StatusBar } from "./components/StatusBar";
import { QueueList } from "./components/QueueList";
import type { SessionState, Command, ServerMessage } from "./types";

export default function App() {
  const [sessions, setSessions] = useState<Record<string, SessionState>>({});

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case "snapshot":
        setSessions(msg.sessions);
        break;
      case "event": {
        const { event } = msg;
        setSessions((prev) => ({
          ...prev,
          [event.session_id]: {
            session_id: event.session_id,
            tab_name: event.tab_name,
            status: event.event_type,
            tail_output: event.tail_output,
            summary: event.summary || "",
            last_event_time: event.timestamp,
          },
        }));
        if (msg.queue_item && Notification.permission === "granted") {
          new Notification(`Claude Code: ${event.tab_name}`, {
            body: event.event_type.replace("_", " "),
          });
        }
        break;
      }
    }
  }, []);

  const { connected, sendCommand } = useWebSocket(handleMessage);

  const handleCommand = useCallback(
    (cmd: Command) => {
      sendCommand(cmd);
      if (cmd.command === "send_text") {
        setSessions((prev) => {
          const s = prev[cmd.session_id];
          if (!s) return prev;
          return { ...prev, [cmd.session_id]: { ...s, status: "working" } };
        });
      }
    },
    [sendCommand]
  );

  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    Notification.requestPermission();
  }

  const attention = Object.values(sessions).filter(
    (s) => s.status === "ready" || s.status === "needs_input" || s.status === "permission_prompt"
  ).length;
  const working = Object.values(sessions).filter((s) => s.status === "working").length;
  const idle = Object.values(sessions).filter((s) => s.status === "idle").length;

  return (
    <div className="app">
      <StatusBar connected={connected} attentionCount={attention} workingCount={working} idleCount={idle} />
      <main>
        <QueueList sessions={sessions} onCommand={handleCommand} />
      </main>
    </div>
  );
}
