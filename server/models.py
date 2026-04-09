from pydantic import BaseModel, Field
from typing import Literal
import time
import uuid


class SessionState(BaseModel):
    session_id: str
    tab_name: str
    status: Literal["working", "ready", "needs_input", "permission_prompt", "idle"] = "working"
    tail_output: str = ""
    last_event_time: float = Field(default_factory=time.time)


class QueueItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str
    event_type: str
    tail_output: str
    status: Literal["pending", "seen", "resolved"] = "pending"
    created_at: float = Field(default_factory=time.time)


class MonitorEvent(BaseModel):
    session_id: str
    tab_name: str
    event_type: Literal["ready", "needs_input", "permission_prompt", "working"]
    tail_output: str = ""
    full_output: str = ""
    timestamp: float = Field(default_factory=time.time)


class Command(BaseModel):
    command: Literal["send_text", "focus_tab", "get_history"]
    session_id: str
    payload: dict = Field(default_factory=dict)
