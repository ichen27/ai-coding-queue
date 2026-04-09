interface StatusBarProps {
  connected: boolean;
  attentionCount: number;
  workingCount: number;
  idleCount: number;
}

export function StatusBar({ connected, attentionCount, workingCount, idleCount }: StatusBarProps) {
  return (
    <header className="status-bar">
      <h1>Claude Code Command Center</h1>
      <div className="status-badges">
        {attentionCount > 0 && (
          <span className="badge badge-attention">{attentionCount} needs attention</span>
        )}
        <span className="badge badge-working">{workingCount} working</span>
        <span className="badge badge-idle">{idleCount} idle</span>
        <span className={`connection-dot ${connected ? "connected" : "disconnected"}`} />
      </div>
    </header>
  );
}
