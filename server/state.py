from server.models import SessionState, QueueItem, MonitorEvent


class StateManager:
    def __init__(self):
        self.sessions: dict[str, SessionState] = {}
        self.queue: list[QueueItem] = []
        self.full_outputs: dict[str, str] = {}

    def process_event(self, event: MonitorEvent) -> QueueItem | None:
        sid = event.session_id
        if sid in self.sessions:
            session = self.sessions[sid]
            session.status = event.event_type
            session.tail_output = event.tail_output
            session.tab_name = event.tab_name
            session.last_event_time = event.timestamp
        else:
            self.sessions[sid] = SessionState(
                session_id=sid, tab_name=event.tab_name, status=event.event_type,
                tail_output=event.tail_output, last_event_time=event.timestamp,
            )
        if event.full_output:
            self.full_outputs[sid] = event.full_output
        if event.event_type == "working":
            for item in self.queue:
                if item.session_id == sid and item.status == "pending":
                    item.status = "resolved"
            return None
        if event.event_type in ("ready", "needs_input", "permission_prompt"):
            has_pending = any(q.session_id == sid and q.status == "pending" for q in self.queue)
            if not has_pending:
                item = QueueItem(session_id=sid, event_type=event.event_type, tail_output=event.tail_output)
                self.queue.append(item)
                return item
        return None

    def resolve_queue_item(self, item_id: str) -> bool:
        for item in self.queue:
            if item.id == item_id:
                item.status = "resolved"
                return True
        return False

    def get_grouped_sessions(self) -> dict[str, list[SessionState]]:
        groups: dict[str, list[SessionState]] = {"attention": [], "working": [], "idle": []}
        for session in self.sessions.values():
            if session.status in ("ready", "needs_input", "permission_prompt"):
                groups["attention"].append(session)
            elif session.status == "working":
                groups["working"].append(session)
            else:
                groups["idle"].append(session)
        return groups

    def get_full_output(self, session_id: str) -> str:
        return self.full_outputs.get(session_id, "")

    def get_snapshot(self) -> dict:
        return {
            "sessions": {sid: s.model_dump() for sid, s in self.sessions.items()},
            "queue": [q.model_dump() for q in self.queue],
        }
