import { useState, useEffect, useRef, type KeyboardEvent } from "react";
import type { SessionState, Command } from "../types";

interface SessionCardProps {
  session: SessionState;
  onCommand: (cmd: Command) => void;
}

const STATUS_COLORS: Record<string, string> = {
  permission_prompt: "card-red",
  needs_input: "card-yellow",
  ready: "card-green",
  working: "card-blue",
  idle: "card-gray",
};

export function SessionCard({ session, onCommand }: SessionCardProps) {
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
      onCommand({
        command: "rename_tab",
        session_id: session.session_id,
        payload: { name },
      });
    }
    setEditing(false);
  }

  function handleEditKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") { e.preventDefault(); commitRename(); }
    if (e.key === "Escape") { setEditing(false); }
  }

  function sendReply() {
    if (!reply.trim()) return;
    onCommand({
      command: "send_text",
      session_id: session.session_id,
      payload: { text: reply },
    });
    setReply("");
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendReply();
    }
  }

  function jumpToTab() {
    onCommand({
      command: "focus_tab",
      session_id: session.session_id,
      payload: {},
    });
  }

  const colorClass = STATUS_COLORS[session.status] || "card-gray";
  const needsReply = session.status === "ready" || session.status === "needs_input";
  const isPermission = session.status === "permission_prompt";
  const lastPrompt = session.summary;

  return (
    <div className={`session-card ${colorClass}`}>
      <div className="card-header">
        <div className="card-title-area">
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
            <span className="tab-name" onDoubleClick={startEditing}>
              {session.tab_name || session.session_id}
            </span>
          )}
          {lastPrompt && (
            <span className="last-prompt">{lastPrompt}</span>
          )}
        </div>
        <div className="card-header-right">
          <span className="status-label">{session.status.replace("_", " ")}</span>
          <button className="btn btn-link" onClick={jumpToTab}>Jump to Tab</button>
        </div>
      </div>

      {session.tail_output && (
        <pre ref={outputRef} className="terminal-output">{session.tail_output}</pre>
      )}

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

      {needsReply && (
        <div className="reply-box">
          <input type="text" value={reply} onChange={(e) => setReply(e.target.value)} onKeyDown={handleKeyDown} placeholder="Type your response..." className="reply-input" />
          <button className="btn btn-send" onClick={sendReply}>Send</button>
        </div>
      )}
    </div>
  );
}
