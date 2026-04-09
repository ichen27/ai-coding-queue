import { useState, useEffect, useRef } from "react";

interface HistoryPanelProps {
  sessionId: string;
}

export function HistoryPanel({ sessionId }: HistoryPanelProps) {
  const [output, setOutput] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const preRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/sessions/${sessionId}/history`)
      .then((r) => r.json())
      .then((data) => {
        setOutput(data.output || "No history available");
        setLoading(false);
      })
      .catch(() => {
        setOutput("Failed to load history");
        setLoading(false);
      });
  }, [sessionId]);

  useEffect(() => {
    if (preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight;
    }
  }, [output]);

  if (loading) return <div className="history-panel">Loading...</div>;

  return (
    <div className="history-panel">
      <pre ref={preRef}>{output}</pre>
    </div>
  );
}
