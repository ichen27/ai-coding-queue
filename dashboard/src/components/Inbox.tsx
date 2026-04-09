import { useState, useEffect, useRef, type KeyboardEvent } from "react";
import type { SessionState, Command } from "../types";

interface InboxProps {
  sessions: Record<string, SessionState>;
  selected: SessionState | null;
  connected: boolean;
  onSelect: (id: string | null) => void;
  onCommand: (cmd: Command) => void;
}

const STATUS_DOT: Record<string, string> = {
  permission_prompt: "dot-red",
  needs_input: "dot-yellow",
  ready: "dot-green",
  working: "dot-blue",
  idle: "dot-gray",
};

const STATUS_LABEL: Record<string, string> = {
  permission_prompt: "Permission",
  needs_input: "Waiting",
  ready: "Ready",
  working: "Working",
  idle: "Idle",
};

function sortedSessions(sessions: Record<string, SessionState>): SessionState[] {
  return Object.values(sessions).sort((a, b) => b.last_event_time - a.last_event_time);
}

export function Inbox({ sessions, selected, connected, onSelect, onCommand }: InboxProps) {
  const sorted = sortedSessions(sessions);
  const attention = sorted.filter(
    (s) => s.status === "ready" || s.status === "needs_input" || s.status === "permission_prompt"
  ).length;
  const working = sorted.filter((s) => s.status === "working").length;

  return (
    <div className="inbox-layout">
      <div className="inbox-sidebar">
        <div className="inbox-header">
          <div className="inbox-title">
            Claude Code
            <span className={`conn-dot ${connected ? "connected" : "disconnected"}`} />
          </div>
          <div className="inbox-counts">
            {attention > 0 && <span className="count-badge count-attention">{attention}</span>}
            {working > 0 && <span className="count-badge count-working">{working}</span>}
          </div>
        </div>
        <div className="inbox-list">
          {sorted.map((s) => (
            <div
              key={s.session_id}
              className={`inbox-item ${selected?.session_id === s.session_id ? "inbox-item-selected" : ""} ${
                s.status === "permission_prompt" || s.status === "needs_input" || s.status === "ready" ? "inbox-item-attention" : ""
              }`}
              onClick={() => onSelect(s.session_id)}
            >
              <div className="inbox-item-top">
                <span className={`status-dot ${STATUS_DOT[s.status] || "dot-gray"}`} />
                <span className="inbox-item-name">{s.tab_name || s.session_id}</span>
                <span className="inbox-item-status">{STATUS_LABEL[s.status] || s.status}</span>
              </div>
              {s.summary && (
                <div className="inbox-item-prompt">{s.summary}</div>
              )}
            </div>
          ))}
          {sorted.length === 0 && (
            <div className="inbox-empty">No sessions detected</div>
          )}
        </div>
      </div>

      <div className="inbox-detail">
        {selected ? (
          <DetailPane session={selected} onCommand={onCommand} />
        ) : (
          <div className="detail-empty">
            <p>Select a session</p>
          </div>
        )}
      </div>
    </div>
  );
}

function DetailPane({ session, onCommand }: { session: SessionState; onCommand: (cmd: Command) => void }) {
  const [reply, setReply] = useState("");
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const outputRef = useRef<HTMLPreElement>(null);
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [session.tail_output]);

  useEffect(() => {
    if (editing && editRef.current) {
      editRef.current.focus();
      editRef.current.select();
    }
  }, [editing]);

  function startEditing() {
    setEditName(session.tab_name || session.session_id);
    setEditing(true);
  }

  function commitRename() {
    const name = editName.trim();
    if (name && name !== session.tab_name) {
      onCommand({ command: "rename_tab", session_id: session.session_id, payload: { name } });
    }
    setEditing(false);
  }

  function handleEditKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") { e.preventDefault(); commitRename(); }
    if (e.key === "Escape") { setEditing(false); }
  }

  function sendReply() {
    if (!reply.trim()) return;
    onCommand({ command: "send_text", session_id: session.session_id, payload: { text: reply } });
    setReply("");
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendReply(); }
  }

  function jumpToTab() {
    onCommand({ command: "focus_tab", session_id: session.session_id, payload: {} });
  }

  const isPermission = session.status === "permission_prompt";
  const needsReply = session.status === "ready" || session.status === "needs_input";

  return (
    <div className="detail-pane">
      <div className="detail-header">
        <div className="detail-title-row">
          {editing ? (
            <input
              ref={editRef}
              className="tab-name-input"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={handleEditKeyDown}
              onBlur={commitRename}
            />
          ) : (
            <h2 className="detail-name" onDoubleClick={startEditing}>{session.tab_name || session.session_id}</h2>
          )}
          <span className={`detail-status detail-status-${session.status}`}>
            {STATUS_LABEL[session.status] || session.status}
          </span>
        </div>
        <div className="detail-actions">
          {session.summary && <span className="detail-prompt">{session.summary}</span>}
          <button className="btn btn-link" onClick={jumpToTab}>Jump to Tab</button>
        </div>
      </div>

      <pre ref={outputRef} className="detail-output">{session.tail_output || "No output yet"}</pre>

      <div className="detail-footer">
        {isPermission && (
          <div className="quick-actions">
            <button className="btn btn-allow" onClick={() => onCommand({ command: "send_text", session_id: session.session_id, payload: { text: "y" } })}>
              Allow
            </button>
            <button className="btn btn-deny" onClick={() => onCommand({ command: "send_text", session_id: session.session_id, payload: { text: "n" } })}>
              Deny
            </button>
          </div>
        )}
        {(needsReply || isPermission) && (
          <div className="reply-box">
            <input
              type="text"
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your response..."
              className="reply-input"
              autoFocus
            />
            <button className="btn btn-send" onClick={sendReply}>Send</button>
          </div>
        )}
      </div>
    </div>
  );
}
