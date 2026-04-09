import { useState, type KeyboardEvent } from "react";
import type { SessionState, QueueItem, Command } from "../types";
import { HistoryPanel } from "./HistoryPanel";

interface SessionCardProps {
  session: SessionState;
  queueItem?: QueueItem;
  onCommand: (cmd: Command) => void;
}

const STATUS_COLORS: Record<string, string> = {
  permission_prompt: "card-red",
  needs_input: "card-yellow",
  ready: "card-green",
  working: "card-blue",
  idle: "card-gray",
};

export function SessionCard({ session, queueItem: _queueItem, onCommand }: SessionCardProps) {
  const [reply, setReply] = useState("");
  const [showOutput, setShowOutput] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

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

  return (
    <div className={`session-card ${colorClass}`}>
      <div className="card-header">
        <span className="tab-name">{session.tab_name || session.session_id}</span>
        <span className="status-label">{session.status.replace("_", " ")}</span>
      </div>

      {session.summary && (
        <pre className="summary-block">{session.summary}</pre>
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

      <div className="card-actions">
        {session.tail_output && (
          <button className="btn btn-link" onClick={() => setShowOutput(!showOutput)}>
            {showOutput ? "Hide output" : "Show output"}
          </button>
        )}
        <button className="btn btn-link" onClick={() => setShowHistory(!showHistory)}>
          {showHistory ? "Hide history" : "Full history"}
        </button>
        <button className="btn btn-link" onClick={jumpToTab}>Jump to Tab</button>
      </div>

      {showOutput && session.tail_output && (
        <pre className="tail-output">{session.tail_output}</pre>
      )}

      {showHistory && <HistoryPanel sessionId={session.session_id} />}
    </div>
  );
}
