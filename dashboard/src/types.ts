export type SessionStatus = "working" | "ready" | "needs_input" | "permission_prompt" | "idle";

export interface SessionState {
  session_id: string;
  tab_name: string;
  status: SessionStatus;
  tail_output: string;
  summary: string;
  last_event_time: number;
}

export interface QueueItem {
  id: string;
  session_id: string;
  event_type: string;
  tail_output: string;
  status: "pending" | "seen" | "resolved";
  created_at: number;
}

export interface MonitorEvent {
  session_id: string;
  tab_name: string;
  event_type: SessionStatus;
  tail_output: string;
  summary: string;
  full_output: string;
  timestamp: number;
}

export interface Command {
  command: "send_text" | "focus_tab" | "get_history" | "rename_tab";
  session_id: string;
  payload: Record<string, string>;
}

export interface SnapshotMessage {
  type: "snapshot";
  sessions: Record<string, SessionState>;
  queue: QueueItem[];
}

export interface EventMessage {
  type: "event";
  event: MonitorEvent;
  queue_item?: QueueItem;
}

export interface QueueUpdateMessage {
  type: "queue_update";
  queue: QueueItem[];
}

export type ServerMessage = SnapshotMessage | EventMessage | QueueUpdateMessage;
