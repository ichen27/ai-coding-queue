import type { SessionState, QueueItem, Command } from "../types";
import { SessionCard } from "./SessionCard";

interface QueueListProps {
  sessions: Record<string, SessionState>;
  queue: QueueItem[];
  onCommand: (cmd: Command) => void;
}

function groupSessions(sessions: Record<string, SessionState>) {
  const attention: SessionState[] = [];
  const working: SessionState[] = [];
  const idle: SessionState[] = [];

  for (const s of Object.values(sessions)) {
    if (s.status === "ready" || s.status === "needs_input" || s.status === "permission_prompt") {
      attention.push(s);
    } else if (s.status === "working") {
      working.push(s);
    } else {
      idle.push(s);
    }
  }

  attention.sort((a, b) => b.last_event_time - a.last_event_time);
  working.sort((a, b) => b.last_event_time - a.last_event_time);

  return { attention, working, idle };
}

export function QueueList({ sessions, queue, onCommand }: QueueListProps) {
  const { attention, working, idle } = groupSessions(sessions);

  function findQueueItem(sessionId: string): QueueItem | undefined {
    return queue.find((q) => q.session_id === sessionId && q.status === "pending");
  }

  return (
    <div className="queue-list">
      {attention.length > 0 && (
        <section>
          <h2 className="section-title">Needs Attention ({attention.length})</h2>
          {attention.map((s) => (
            <SessionCard key={s.session_id} session={s} queueItem={findQueueItem(s.session_id)} onCommand={onCommand} />
          ))}
        </section>
      )}

      {working.length > 0 && (
        <section>
          <h2 className="section-title">Working ({working.length})</h2>
          {working.map((s) => (
            <SessionCard key={s.session_id} session={s} onCommand={onCommand} />
          ))}
        </section>
      )}

      {idle.length > 0 && (
        <section>
          <h2 className="section-title">Idle ({idle.length})</h2>
          {idle.map((s) => (
            <SessionCard key={s.session_id} session={s} onCommand={onCommand} />
          ))}
        </section>
      )}

      {Object.keys(sessions).length === 0 && (
        <div className="empty-state">
          <p>No Claude Code sessions detected.</p>
          <p>Make sure iTerm2 is running and the monitor script is active.</p>
        </div>
      )}
    </div>
  );
}
