import type { SessionState, Command } from "../types";
import { SessionCard } from "./SessionCard";

interface QueueListProps {
  sessions: Record<string, SessionState>;
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

  // Stable sort: alphabetical by tab name, then by session_id as tiebreaker
  const stableSort = (a: SessionState, b: SessionState) => {
    const nameA = (a.tab_name || a.session_id).toLowerCase();
    const nameB = (b.tab_name || b.session_id).toLowerCase();
    if (nameA < nameB) return -1;
    if (nameA > nameB) return 1;
    return a.session_id < b.session_id ? -1 : 1;
  };

  attention.sort(stableSort);
  working.sort(stableSort);
  idle.sort(stableSort);

  return { attention, working, idle };
}

export function QueueList({ sessions, onCommand }: QueueListProps) {
  const { attention, working, idle } = groupSessions(sessions);

  return (
    <div className="queue-list">
      {attention.length > 0 && (
        <section>
          <h2 className="section-title">Needs Attention ({attention.length})</h2>
          {attention.map((s) => (
            <SessionCard key={s.session_id} session={s} onCommand={onCommand} />
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
