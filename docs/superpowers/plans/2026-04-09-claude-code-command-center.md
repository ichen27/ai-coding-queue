# Claude Code Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a localhost web dashboard that monitors iTerm2 Claude Code sessions, queues notifications, and allows responding inline or jumping to tabs.

**Architecture:** iTerm2 Python monitor script watches sessions and pushes events via WebSocket to a FastAPI backend, which serves a React dashboard. Commands flow back through the same path to send text or focus tabs.

**Tech Stack:** Python 3.14 + iterm2 + FastAPI + uvicorn | React + TypeScript + Vite + Bun

---

## File Map

| File | Responsibility |
|------|---------------|
| `monitor/patterns.py` | Regex/string patterns for detecting Claude Code states |
| `monitor/claude_monitor.py` | iTerm2 AutoLaunch script — watches sessions, pushes events, receives commands |
| `server/models.py` | Pydantic models for events, sessions, queue items, commands |
| `server/state.py` | In-memory state manager — sessions dict, queue list, CRUD operations |
| `server/main.py` | FastAPI app — WebSocket endpoints for monitor + dashboard, REST endpoints, static file serving |
| `server/requirements.txt` | Python dependencies |
| `dashboard/src/types.ts` | TypeScript types mirroring server models |
| `dashboard/src/hooks/useWebSocket.ts` | WebSocket connection hook with reconnect logic |
| `dashboard/src/components/StatusBar.tsx` | Connection status + session count badges |
| `dashboard/src/components/HistoryPanel.tsx` | Expandable full output viewer |
| `dashboard/src/components/SessionCard.tsx` | Session card with status, tail output, reply input, action buttons |
| `dashboard/src/components/QueueList.tsx` | Groups sessions by state, renders SessionCards |
| `dashboard/src/App.tsx` | Root component — connects WebSocket, manages state, renders QueueList + StatusBar |
| `dashboard/src/index.css` | Global styles |
| `dashboard/package.json` | Frontend dependencies |
| `dashboard/vite.config.ts` | Vite config with proxy to backend |
| `dashboard/index.html` | Vite entry HTML |
| `scripts/start.sh` | Starts backend + registers iTerm2 monitor |
| `scripts/stop.sh` | Stops backend + removes monitor symlink |

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `server/requirements.txt`
- Create: `dashboard/package.json`
- Create: `dashboard/vite.config.ts`
- Create: `dashboard/index.html`
- Create: `dashboard/tsconfig.json`

- [ ] **Step 1: Create server requirements**

```
# server/requirements.txt
fastapi==0.115.12
uvicorn[standard]==0.34.2
websockets==15.0.1
```

- [ ] **Step 2: Install Python dependencies**

Run: `cd ~/iterm-dashboard && python3 -m venv .venv && source .venv/bin/activate && pip install -r server/requirements.txt`
Expected: Successfully installed fastapi uvicorn websockets

- [ ] **Step 3: Scaffold dashboard with Vite**

Run: `cd ~/iterm-dashboard && bun create vite dashboard --template react-ts`
Expected: Scaffolding project in ./dashboard

- [ ] **Step 4: Install dashboard dependencies**

Run: `cd ~/iterm-dashboard/dashboard && bun install`
Expected: packages installed

- [ ] **Step 5: Verify both stacks work**

Run: `cd ~/iterm-dashboard && source .venv/bin/activate && python3 -c "import fastapi; print(fastapi.__version__)"`
Expected: 0.115.12

Run: `cd ~/iterm-dashboard/dashboard && bun run build`
Expected: build succeeds

- [ ] **Step 6: Install iterm2 Python package**

Run: `cd ~/iterm-dashboard && source .venv/bin/activate && pip install iterm2`
Expected: Successfully installed iterm2

- [ ] **Step 7: Commit**

```bash
cd ~/iterm-dashboard && git init && git add -A && git commit -m "chore: scaffold project with FastAPI backend and React dashboard"
```

---

### Task 2: Pattern Detection Module

**Files:**
- Create: `monitor/patterns.py`
- Create: `monitor/__init__.py`
- Create: `tests/test_patterns.py`

- [ ] **Step 1: Write failing tests for pattern detection**

```python
# tests/test_patterns.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from monitor.patterns import detect_state

def test_detects_permission_prompt_allow_deny():
    output = """Here's what I found in the codebase.

  Allow  Deny  """
    result = detect_state(output)
    assert result == "permission_prompt"

def test_detects_permission_prompt_yes_no():
    output = """Do you want to proceed?

  Yes  No  """
    result = detect_state(output)
    assert result == "permission_prompt"

def test_detects_claude_input_prompt():
    output = """Done! The file has been updated.

❯ """
    result = detect_state(output)
    assert result == "ready"

def test_detects_claude_input_prompt_dollar():
    output = """Finished running tests.

$ """
    result = detect_state(output)
    assert result == "ready"

def test_detects_question():
    output = """I found two approaches. Should I use the factory pattern or the builder pattern?"""
    result = detect_state(output)
    assert result == "needs_input"

def test_streaming_output():
    output = """Let me check the file structure and understand the codebase.

Reading src/main.py..."""
    result = detect_state(output)
    assert result == "working"

def test_empty_output():
    result = detect_state("")
    assert result == "working"

def test_extracts_tail_output():
    from monitor.patterns import extract_tail
    lines = "\n".join(f"line {i}" for i in range(100))
    tail = extract_tail(lines, 50)
    assert tail.startswith("line 50")
    assert tail.endswith("line 99")
    assert len(tail.split("\n")) == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_patterns.py -v`
Expected: FAILED — ModuleNotFoundError: No module named 'monitor'

- [ ] **Step 3: Implement patterns module**

```python
# monitor/__init__.py
```

```python
# monitor/patterns.py
import re

# Permission prompts — Claude Code shows these when tools need approval
_PERMISSION_PATTERNS = [
    re.compile(r"Allow\s+Deny", re.IGNORECASE),
    re.compile(r"^\s*(Yes|No)\s+(Yes|No)\s*$", re.MULTILINE),
    re.compile(r"\(y/n\)", re.IGNORECASE),
]

# Input prompt — Claude Code is done, waiting for user input
_READY_PATTERNS = [
    re.compile(r"[❯>]\s*$"),
    re.compile(r"\$\s*$"),
]

# Question patterns — Claude is asking something
_QUESTION_PATTERNS = [
    re.compile(r"\?\s*$", re.MULTILINE),
]


def detect_state(output: str) -> str:
    """Analyze terminal output and return the detected Claude Code state.

    Returns one of: "permission_prompt", "ready", "needs_input", "working"
    """
    if not output.strip():
        return "working"

    # Check last ~20 lines for patterns (most relevant context)
    lines = output.strip().split("\n")
    recent = "\n".join(lines[-20:])

    # Highest priority: permission prompts
    for pattern in _PERMISSION_PATTERNS:
        if pattern.search(recent):
            return "permission_prompt"

    # Ready prompt — Claude is done, user's turn
    for pattern in _READY_PATTERNS:
        if pattern.search(recent):
            return "ready"

    # Question — Claude is asking something
    for pattern in _QUESTION_PATTERNS:
        if pattern.search(lines[-1]):
            return "needs_input"

    return "working"


def extract_tail(output: str, num_lines: int = 50) -> str:
    """Extract the last N lines from output."""
    lines = output.split("\n")
    if len(lines) <= num_lines:
        return output
    return "\n".join(lines[-num_lines:])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_patterns.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/iterm-dashboard && git add monitor/ tests/ && git commit -m "feat: add Claude Code output pattern detection"
```

---

### Task 3: Server Models

**Files:**
- Create: `server/__init__.py`
- Create: `server/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for models**

```python
# tests/test_models.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.models import SessionState, QueueItem, MonitorEvent, Command
import time

def test_session_state_creation():
    s = SessionState(
        session_id="abc-123",
        tab_name="deer-flow",
        status="working",
        tail_output="",
        last_event_time=time.time(),
    )
    assert s.session_id == "abc-123"
    assert s.status == "working"

def test_queue_item_creation():
    q = QueueItem(
        session_id="abc-123",
        event_type="ready",
        tail_output="Done!",
    )
    assert q.id  # auto-generated
    assert q.status == "pending"
    assert q.created_at > 0

def test_monitor_event_creation():
    e = MonitorEvent(
        session_id="abc-123",
        tab_name="deer-flow",
        event_type="ready",
        tail_output="Done!",
        full_output="Full history here",
    )
    assert e.timestamp > 0

def test_command_creation():
    c = Command(
        command="send_text",
        session_id="abc-123",
        payload={"text": "yes"},
    )
    assert c.command == "send_text"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_models.py -v`
Expected: FAILED — ModuleNotFoundError

- [ ] **Step 3: Implement models**

```python
# server/__init__.py
```

```python
# server/models.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_models.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/iterm-dashboard && git add server/ tests/test_models.py && git commit -m "feat: add Pydantic models for events, sessions, queue items, commands"
```

---

### Task 4: In-Memory State Manager

**Files:**
- Create: `server/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_state.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.state import StateManager
from server.models import MonitorEvent

def test_process_event_creates_session():
    sm = StateManager()
    event = MonitorEvent(
        session_id="s1",
        tab_name="my-tab",
        event_type="working",
        tail_output="streaming...",
    )
    sm.process_event(event)
    assert "s1" in sm.sessions
    assert sm.sessions["s1"].tab_name == "my-tab"
    assert sm.sessions["s1"].status == "working"

def test_process_event_updates_session():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="working", tail_output=""))
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    assert sm.sessions["s1"].status == "ready"
    assert sm.sessions["s1"].tail_output == "Done!"

def test_process_event_creates_queue_item_for_attention():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    assert len(sm.queue) == 1
    assert sm.queue[0].event_type == "ready"
    assert sm.queue[0].status == "pending"

def test_process_event_no_queue_for_working():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="working", tail_output=""))
    assert len(sm.queue) == 0

def test_process_event_resolves_old_queue_items():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    assert len(sm.queue) == 1
    # Session goes back to working (user responded externally)
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="working", tail_output=""))
    assert sm.queue[0].status == "resolved"

def test_resolve_queue_item():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    item_id = sm.queue[0].id
    sm.resolve_queue_item(item_id)
    assert sm.queue[0].status == "resolved"

def test_get_grouped_sessions():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab1", event_type="ready", tail_output=""))
    sm.process_event(MonitorEvent(session_id="s2", tab_name="tab2", event_type="working", tail_output=""))
    sm.process_event(MonitorEvent(session_id="s3", tab_name="tab3", event_type="permission_prompt", tail_output=""))
    groups = sm.get_grouped_sessions()
    assert len(groups["attention"]) == 2  # ready + permission_prompt
    assert len(groups["working"]) == 1
    assert len(groups["idle"]) == 0

def test_no_duplicate_queue_items():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    pending = [q for q in sm.queue if q.status == "pending"]
    assert len(pending) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_state.py -v`
Expected: FAILED — ModuleNotFoundError

- [ ] **Step 3: Implement state manager**

```python
# server/state.py
from server.models import SessionState, QueueItem, MonitorEvent


class StateManager:
    def __init__(self):
        self.sessions: dict[str, SessionState] = {}
        self.queue: list[QueueItem] = []
        self.full_outputs: dict[str, str] = {}

    def process_event(self, event: MonitorEvent) -> QueueItem | None:
        """Process a monitor event. Updates session state and creates queue items as needed."""
        sid = event.session_id

        # Update or create session
        if sid in self.sessions:
            session = self.sessions[sid]
            old_status = session.status
            session.status = event.event_type
            session.tail_output = event.tail_output
            session.tab_name = event.tab_name
            session.last_event_time = event.timestamp
        else:
            self.sessions[sid] = SessionState(
                session_id=sid,
                tab_name=event.tab_name,
                status=event.event_type,
                tail_output=event.tail_output,
                last_event_time=event.timestamp,
            )

        # Store full output
        if event.full_output:
            self.full_outputs[sid] = event.full_output

        # If session goes back to "working", resolve any pending queue items for it
        if event.event_type == "working":
            for item in self.queue:
                if item.session_id == sid and item.status == "pending":
                    item.status = "resolved"
            return None

        # For attention states, create a queue item (if not duplicate)
        if event.event_type in ("ready", "needs_input", "permission_prompt"):
            # Check for existing pending item for this session
            has_pending = any(
                q.session_id == sid and q.status == "pending"
                for q in self.queue
            )
            if not has_pending:
                item = QueueItem(
                    session_id=sid,
                    event_type=event.event_type,
                    tail_output=event.tail_output,
                )
                self.queue.append(item)
                return item

        return None

    def resolve_queue_item(self, item_id: str) -> bool:
        """Mark a queue item as resolved."""
        for item in self.queue:
            if item.id == item_id:
                item.status = "resolved"
                return True
        return False

    def get_grouped_sessions(self) -> dict[str, list[SessionState]]:
        """Group sessions by attention status."""
        groups: dict[str, list[SessionState]] = {
            "attention": [],
            "working": [],
            "idle": [],
        }
        for session in self.sessions.values():
            if session.status in ("ready", "needs_input", "permission_prompt"):
                groups["attention"].append(session)
            elif session.status == "working":
                groups["working"].append(session)
            else:
                groups["idle"].append(session)
        return groups

    def get_full_output(self, session_id: str) -> str:
        """Get full output for a session."""
        return self.full_outputs.get(session_id, "")

    def get_snapshot(self) -> dict:
        """Get full state snapshot for dashboard initial load."""
        return {
            "sessions": {sid: s.model_dump() for sid, s in self.sessions.items()},
            "queue": [q.model_dump() for q in self.queue],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_state.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/iterm-dashboard && git add server/state.py tests/test_state.py && git commit -m "feat: add in-memory state manager for sessions and queue"
```

---

### Task 5: FastAPI Backend Server

**Files:**
- Create: `server/main.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_server.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from server.main import app, state

@pytest.fixture(autouse=True)
def reset_state():
    state.sessions.clear()
    state.queue.clear()
    state.full_outputs.clear()
    yield

def test_get_sessions_empty():
    client = TestClient(app)
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessions"] == {}
    assert data["queue"] == []

def test_respond_to_session_no_session():
    client = TestClient(app)
    resp = client.post("/api/sessions/nonexistent/respond", json={"text": "hello"})
    assert resp.status_code == 404

def test_dashboard_websocket_receives_snapshot():
    client = TestClient(app)
    with client.websocket_connect("/ws/dashboard") as ws:
        data = ws.receive_json()
        assert data["type"] == "snapshot"
        assert "sessions" in data
        assert "queue" in data

def test_monitor_websocket_processes_event():
    client = TestClient(app)
    # Connect dashboard first to receive broadcasts
    with client.websocket_connect("/ws/dashboard") as dash_ws:
        snapshot = dash_ws.receive_json()
        assert snapshot["type"] == "snapshot"

        # Connect monitor and send event
        with client.websocket_connect("/ws/monitor") as mon_ws:
            mon_ws.send_json({
                "session_id": "s1",
                "tab_name": "test-tab",
                "event_type": "ready",
                "tail_output": "Done!",
                "full_output": "Full history",
            })
            # Dashboard should receive the event broadcast
            data = dash_ws.receive_json()
            assert data["type"] == "event"
            assert data["event"]["session_id"] == "s1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_server.py -v`
Expected: FAILED — cannot import 'main'

- [ ] **Step 3: Implement server**

```python
# server/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import json

from server.state import StateManager
from server.models import MonitorEvent, Command

app = FastAPI(title="Claude Code Command Center")
state = StateManager()

# Connected WebSocket clients
monitor_ws: WebSocket | None = None
dashboard_clients: list[WebSocket] = []


class RespondRequest(BaseModel):
    text: str


async def broadcast_to_dashboards(message: dict):
    """Send a message to all connected dashboard clients."""
    disconnected = []
    for ws in dashboard_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        dashboard_clients.remove(ws)


@app.websocket("/ws/monitor")
async def monitor_websocket(ws: WebSocket):
    """WebSocket endpoint for the iTerm2 monitor script."""
    global monitor_ws
    await ws.accept()
    monitor_ws = ws
    try:
        while True:
            data = await ws.receive_json()
            event = MonitorEvent(**data)
            queue_item = state.process_event(event)

            # Broadcast to all dashboards
            msg = {
                "type": "event",
                "event": event.model_dump(),
            }
            if queue_item:
                msg["queue_item"] = queue_item.model_dump()
            await broadcast_to_dashboards(msg)
    except WebSocketDisconnect:
        monitor_ws = None


@app.websocket("/ws/dashboard")
async def dashboard_websocket(ws: WebSocket):
    """WebSocket endpoint for dashboard clients."""
    await ws.accept()
    dashboard_clients.append(ws)

    # Send initial snapshot
    await ws.send_json({"type": "snapshot", **state.get_snapshot()})

    try:
        while True:
            data = await ws.receive_json()
            command = Command(**data)

            # Forward command to monitor
            if monitor_ws:
                await monitor_ws.send_json(command.model_dump())

            # If it's a send_text command, resolve the queue item for this session
            if command.command == "send_text":
                for item in state.queue:
                    if item.session_id == command.session_id and item.status == "pending":
                        item.status = "resolved"
                        break
                await broadcast_to_dashboards({
                    "type": "queue_update",
                    "queue": [q.model_dump() for q in state.queue],
                })
    except WebSocketDisconnect:
        if ws in dashboard_clients:
            dashboard_clients.remove(ws)


@app.get("/api/sessions")
async def get_sessions():
    """Get all sessions and queue state."""
    return state.get_snapshot()


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """Get full output history for a session."""
    if session_id not in state.sessions:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    return {"session_id": session_id, "output": state.get_full_output(session_id)}


@app.post("/api/sessions/{session_id}/respond")
async def respond_to_session(session_id: str, req: RespondRequest):
    """Send text to a session (REST fallback)."""
    if session_id not in state.sessions:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Session not found"})

    # Forward to monitor
    if monitor_ws:
        await monitor_ws.send_json({
            "command": "send_text",
            "session_id": session_id,
            "payload": {"text": req.text},
        })

    # Resolve queue items
    for item in state.queue:
        if item.session_id == session_id and item.status == "pending":
            item.status = "resolved"
            break

    return {"ok": True}


# Serve dashboard static files (production build)
dashboard_dist = Path(__file__).parent.parent / "dashboard" / "dist"
if dashboard_dist.exists():
    app.mount("/assets", StaticFiles(directory=dashboard_dist / "assets"), name="assets")

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(dashboard_dist / "index.html")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_server.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/iterm-dashboard && git add server/main.py tests/test_server.py && git commit -m "feat: add FastAPI backend with WebSocket endpoints for monitor and dashboard"
```

---

### Task 6: Dashboard TypeScript Types & WebSocket Hook

**Files:**
- Create: `dashboard/src/types.ts`
- Create: `dashboard/src/hooks/useWebSocket.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// dashboard/src/types.ts
export type SessionStatus = "working" | "ready" | "needs_input" | "permission_prompt" | "idle";

export interface SessionState {
  session_id: string;
  tab_name: string;
  status: SessionStatus;
  tail_output: string;
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
  full_output: string;
  timestamp: number;
}

export interface Command {
  command: "send_text" | "focus_tab" | "get_history";
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
```

- [ ] **Step 2: Create WebSocket hook**

```typescript
// dashboard/src/hooks/useWebSocket.ts
import { useEffect, useRef, useState, useCallback } from "react";
import type { ServerMessage, Command } from "../types";

const WS_URL = `ws://${window.location.host}/ws/dashboard`;
const RECONNECT_DELAY = 2000;

export function useWebSocket(onMessage: (msg: ServerMessage) => void) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let ws: WebSocket;

    function connect() {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data) as ServerMessage;
        onMessageRef.current(data);
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  const sendCommand = useCallback((cmd: Command) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  return { connected, sendCommand };
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/iterm-dashboard && git add dashboard/src/types.ts dashboard/src/hooks/ && git commit -m "feat: add TypeScript types and WebSocket hook for dashboard"
```

---

### Task 7: Dashboard Components

**Files:**
- Create: `dashboard/src/components/StatusBar.tsx`
- Create: `dashboard/src/components/HistoryPanel.tsx`
- Create: `dashboard/src/components/SessionCard.tsx`
- Create: `dashboard/src/components/QueueList.tsx`

- [ ] **Step 1: Create StatusBar component**

```tsx
// dashboard/src/components/StatusBar.tsx
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
```

- [ ] **Step 2: Create HistoryPanel component**

```tsx
// dashboard/src/components/HistoryPanel.tsx
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
```

- [ ] **Step 3: Create SessionCard component**

```tsx
// dashboard/src/components/SessionCard.tsx
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

export function SessionCard({ session, queueItem, onCommand }: SessionCardProps) {
  const [reply, setReply] = useState("");
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

      {session.tail_output && (
        <pre className="tail-output">{session.tail_output}</pre>
      )}

      {isPermission && (
        <div className="quick-actions">
          <button
            className="btn btn-allow"
            onClick={() =>
              onCommand({ command: "send_text", session_id: session.session_id, payload: { text: "y" } })
            }
          >
            Allow
          </button>
          <button
            className="btn btn-deny"
            onClick={() =>
              onCommand({ command: "send_text", session_id: session.session_id, payload: { text: "n" } })
            }
          >
            Deny
          </button>
        </div>
      )}

      {needsReply && (
        <div className="reply-box">
          <input
            type="text"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your response..."
            className="reply-input"
          />
          <button className="btn btn-send" onClick={sendReply}>
            Send
          </button>
        </div>
      )}

      <div className="card-actions">
        <button className="btn btn-link" onClick={() => setShowHistory(!showHistory)}>
          {showHistory ? "Hide history" : "Show history"}
        </button>
        <button className="btn btn-link" onClick={jumpToTab}>
          Jump to Tab
        </button>
      </div>

      {showHistory && <HistoryPanel sessionId={session.session_id} />}
    </div>
  );
}
```

- [ ] **Step 4: Create QueueList component**

```tsx
// dashboard/src/components/QueueList.tsx
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

  // Sort attention by most recent first
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
            <SessionCard
              key={s.session_id}
              session={s}
              queueItem={findQueueItem(s.session_id)}
              onCommand={onCommand}
            />
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
```

- [ ] **Step 5: Commit**

```bash
cd ~/iterm-dashboard && git add dashboard/src/components/ && git commit -m "feat: add dashboard components — StatusBar, HistoryPanel, SessionCard, QueueList"
```

---

### Task 8: App Root & Styles

**Files:**
- Modify: `dashboard/src/App.tsx`
- Create: `dashboard/src/index.css`

- [ ] **Step 1: Write App.tsx**

```tsx
// dashboard/src/App.tsx
import { useCallback, useState } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { StatusBar } from "./components/StatusBar";
import { QueueList } from "./components/QueueList";
import type { SessionState, QueueItem, Command, ServerMessage } from "./types";

export default function App() {
  const [sessions, setSessions] = useState<Record<string, SessionState>>({});
  const [queue, setQueue] = useState<QueueItem[]>([]);

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case "snapshot":
        setSessions(msg.sessions);
        setQueue(msg.queue);
        break;
      case "event": {
        const { event, queue_item } = msg;
        setSessions((prev) => ({
          ...prev,
          [event.session_id]: {
            session_id: event.session_id,
            tab_name: event.tab_name,
            status: event.event_type,
            tail_output: event.tail_output,
            last_event_time: event.timestamp,
          },
        }));
        if (queue_item) {
          setQueue((prev) => [...prev, queue_item]);
          // Browser notification
          if (Notification.permission === "granted") {
            new Notification(`Claude Code: ${event.tab_name}`, {
              body: event.event_type.replace("_", " "),
            });
          }
        }
        break;
      }
      case "queue_update":
        setQueue(msg.queue);
        break;
    }
  }, []);

  const { connected, sendCommand } = useWebSocket(handleMessage);

  const handleCommand = useCallback(
    (cmd: Command) => {
      sendCommand(cmd);
      // Optimistic update: if sending text, mark session as working
      if (cmd.command === "send_text") {
        setSessions((prev) => {
          const s = prev[cmd.session_id];
          if (!s) return prev;
          return { ...prev, [cmd.session_id]: { ...s, status: "working" } };
        });
        setQueue((prev) =>
          prev.map((q) =>
            q.session_id === cmd.session_id && q.status === "pending"
              ? { ...q, status: "resolved" as const }
              : q
          )
        );
      }
    },
    [sendCommand]
  );

  // Request notification permission on mount
  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    Notification.requestPermission();
  }

  const attention = Object.values(sessions).filter(
    (s) => s.status === "ready" || s.status === "needs_input" || s.status === "permission_prompt"
  ).length;
  const working = Object.values(sessions).filter((s) => s.status === "working").length;
  const idle = Object.values(sessions).filter((s) => s.status === "idle").length;

  return (
    <div className="app">
      <StatusBar
        connected={connected}
        attentionCount={attention}
        workingCount={working}
        idleCount={idle}
      />
      <main>
        <QueueList sessions={sessions} queue={queue} onCommand={handleCommand} />
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Write styles**

```css
/* dashboard/src/index.css */
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --red: #f85149;
  --yellow: #d29922;
  --green: #3fb950;
  --blue: #58a6ff;
  --gray: #484f58;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}

.app {
  max-width: 900px;
  margin: 0 auto;
  padding: 16px;
}

/* Status Bar */
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}

.status-bar h1 {
  font-size: 18px;
  font-weight: 600;
}

.status-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}

.badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.badge-attention { background: rgba(248, 81, 73, 0.2); color: var(--red); }
.badge-working { background: rgba(88, 166, 255, 0.2); color: var(--blue); }
.badge-idle { background: rgba(72, 79, 88, 0.2); color: var(--text-muted); }

.connection-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 8px;
}

.connected { background: var(--green); }
.disconnected { background: var(--red); }

/* Section Titles */
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 20px 0 10px;
}

/* Session Cards */
.session-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 10px;
  border-left: 3px solid var(--gray);
}

.card-red { border-left-color: var(--red); }
.card-yellow { border-left-color: var(--yellow); }
.card-green { border-left-color: var(--green); }
.card-blue { border-left-color: var(--blue); }
.card-gray { border-left-color: var(--gray); }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.tab-name {
  font-weight: 600;
  font-size: 15px;
}

.status-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: capitalize;
}

.tail-output {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  background: var(--bg);
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 10px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-muted);
}

/* Quick Actions */
.quick-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

/* Reply Box */
.reply-box {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.reply-input {
  flex: 1;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  color: var(--text);
  font-size: 14px;
  outline: none;
}

.reply-input:focus {
  border-color: var(--blue);
}

/* Buttons */
.btn {
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
}

.btn-allow { background: rgba(63, 185, 80, 0.2); color: var(--green); }
.btn-allow:hover { background: rgba(63, 185, 80, 0.3); }
.btn-deny { background: rgba(248, 81, 73, 0.2); color: var(--red); }
.btn-deny:hover { background: rgba(248, 81, 73, 0.3); }
.btn-send { background: rgba(88, 166, 255, 0.2); color: var(--blue); }
.btn-send:hover { background: rgba(88, 166, 255, 0.3); }

.btn-link {
  background: none;
  color: var(--text-muted);
  padding: 4px 0;
  font-size: 12px;
}

.btn-link:hover { color: var(--text); }

/* Card Actions */
.card-actions {
  display: flex;
  gap: 16px;
}

/* History Panel */
.history-panel {
  margin-top: 10px;
  max-height: 400px;
  overflow-y: auto;
}

.history-panel pre {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
  background: var(--bg);
  padding: 10px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-muted);
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-muted);
}

.empty-state p {
  margin-bottom: 8px;
}
```

- [ ] **Step 3: Update main.tsx entry point**

```tsx
// dashboard/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 4: Build and verify**

Run: `cd ~/iterm-dashboard/dashboard && bun run build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
cd ~/iterm-dashboard && git add dashboard/src/ && git commit -m "feat: add dashboard App root, styles, and entry point"
```

---

### Task 9: iTerm2 Monitor Script

**Files:**
- Create: `monitor/claude_monitor.py`

- [ ] **Step 1: Write the monitor script**

```python
#!/usr/bin/env python3
"""
Claude Code Command Center — iTerm2 Monitor Script

AutoLaunch script that watches all iTerm2 sessions for Claude Code activity
and pushes events to the backend server via WebSocket.
"""

import asyncio
import json
import iterm2
import websockets

from patterns import detect_state, extract_tail

SERVER_URL = "ws://localhost:7890/ws/monitor"
POLL_INTERVAL = 2.0  # seconds between checks
IDLE_THRESHOLD = 3.0  # seconds of no output change to consider idle

# Track previous state per session to avoid duplicate events
_prev_content: dict[str, str] = {}
_prev_state: dict[str, str] = {}
_last_change_time: dict[str, float] = {}


async def connect_to_server():
    """Connect to the backend WebSocket, retry on failure."""
    while True:
        try:
            ws = await websockets.connect(SERVER_URL)
            print(f"[monitor] Connected to {SERVER_URL}")
            return ws
        except Exception as e:
            print(f"[monitor] Connection failed ({e}), retrying in 3s...")
            await asyncio.sleep(3)


async def handle_commands(ws, app):
    """Listen for commands from the backend and execute them."""
    try:
        async for raw in ws:
            data = json.loads(raw)
            cmd = data.get("command")
            sid = data.get("session_id")
            payload = data.get("payload", {})

            session = None
            for window in app.terminal_windows:
                for tab in window.tabs:
                    for s in tab.sessions:
                        if s.session_id == sid:
                            session = s
                            break

            if not session:
                print(f"[monitor] Session {sid} not found")
                continue

            if cmd == "send_text":
                text = payload.get("text", "")
                await session.async_send_text(text + "\n")
                print(f"[monitor] Sent text to {sid}: {text[:50]}")

            elif cmd == "focus_tab":
                for window in app.terminal_windows:
                    for tab in window.tabs:
                        if session in tab.sessions:
                            await tab.async_activate()
                            await window.async_activate()
                            print(f"[monitor] Focused tab for {sid}")
                            break

            elif cmd == "get_history":
                contents = await session.async_get_contents()
                lines = []
                for line in contents:
                    lines.append(line.string)
                # Send back via a separate channel or REST — for now, log it
                print(f"[monitor] History requested for {sid}: {len(lines)} lines")

    except websockets.ConnectionClosed:
        print("[monitor] Server connection lost in command handler")


async def poll_sessions(ws, app):
    """Periodically check all sessions for state changes."""
    while True:
        try:
            now = asyncio.get_event_loop().time()

            for window in app.terminal_windows:
                for tab in window.tabs:
                    tab_name = await tab.async_get_variable("titleOverride") or tab.tab_id
                    for session in tab.sessions:
                        sid = session.session_id

                        try:
                            contents = await session.async_get_contents()
                        except Exception:
                            continue

                        full_text = "\n".join(line.string for line in contents)

                        # Check if content changed
                        prev = _prev_content.get(sid, "")
                        if full_text != prev:
                            _prev_content[sid] = full_text
                            _last_change_time[sid] = now

                        # Detect state from output
                        state = detect_state(full_text)

                        # Idle fallback: if content hasn't changed for IDLE_THRESHOLD
                        time_since_change = now - _last_change_time.get(sid, now)
                        if state == "working" and time_since_change > IDLE_THRESHOLD:
                            state = "ready"

                        # Only send event if state changed
                        prev_state = _prev_state.get(sid)
                        if state != prev_state:
                            _prev_state[sid] = state

                            event = {
                                "session_id": sid,
                                "tab_name": str(tab_name),
                                "event_type": state,
                                "tail_output": extract_tail(full_text, 50),
                                "full_output": full_text,
                                "timestamp": now,
                            }

                            try:
                                await ws.send(json.dumps(event))
                            except websockets.ConnectionClosed:
                                print("[monitor] Lost connection while sending")
                                return

        except Exception as e:
            print(f"[monitor] Poll error: {e}")

        await asyncio.sleep(POLL_INTERVAL)


async def main(connection):
    app = await iterm2.async_get_app(connection)
    if not app:
        print("[monitor] Could not get iTerm2 app")
        return

    print("[monitor] Starting Claude Code Command Center monitor")

    while True:
        ws = await connect_to_server()

        # Run polling and command handling concurrently
        poll_task = asyncio.create_task(poll_sessions(ws, app))
        cmd_task = asyncio.create_task(handle_commands(ws, app))

        # Wait until either task ends (connection lost)
        done, pending = await asyncio.wait(
            [poll_task, cmd_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

        try:
            await ws.close()
        except Exception:
            pass

        print("[monitor] Reconnecting in 3s...")
        await asyncio.sleep(3)


iterm2.run_forever(main)
```

- [ ] **Step 2: Commit**

```bash
cd ~/iterm-dashboard && git add monitor/claude_monitor.py && git commit -m "feat: add iTerm2 monitor script — watches sessions, pushes events, handles commands"
```

---

### Task 10: Startup & Shutdown Scripts

**Files:**
- Create: `scripts/start.sh`
- Create: `scripts/stop.sh`

- [ ] **Step 1: Create start script**

```bash
#!/bin/bash
# scripts/start.sh — Start the Claude Code Command Center
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$DIR/.server.pid"
AUTOLAUNCH_DIR="$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch"
SYMLINK_PATH="$AUTOLAUNCH_DIR/claude_monitor.py"

echo "=== Claude Code Command Center ==="

# 1. Build dashboard if needed
if [ ! -d "$DIR/dashboard/dist" ]; then
  echo "[build] Building dashboard..."
  cd "$DIR/dashboard" && bun run build
fi

# 2. Start FastAPI server
echo "[server] Starting backend on http://localhost:7890 ..."
cd "$DIR"
source .venv/bin/activate
uvicorn server.main:app --host 127.0.0.1 --port 7890 &
echo $! > "$PIDFILE"
echo "[server] PID: $(cat "$PIDFILE")"

# 3. Register iTerm2 monitor
mkdir -p "$AUTOLAUNCH_DIR"
if [ -L "$SYMLINK_PATH" ] || [ -e "$SYMLINK_PATH" ]; then
  rm "$SYMLINK_PATH"
fi
ln -s "$DIR/monitor/claude_monitor.py" "$SYMLINK_PATH"
echo "[monitor] Symlinked monitor to iTerm2 AutoLaunch"

# 4. Try to trigger the script if iTerm2 is running
if pgrep -x "iTerm2" > /dev/null; then
  echo "[monitor] iTerm2 is running. The monitor will activate on next iTerm2 restart,"
  echo "          or you can run: Scripts > claude_monitor.py from the iTerm2 menu."
fi

echo ""
echo "Dashboard: http://localhost:7890"
echo "To stop:   ./scripts/stop.sh"
```

- [ ] **Step 2: Create stop script**

```bash
#!/bin/bash
# scripts/stop.sh — Stop the Claude Code Command Center
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$DIR/.server.pid"
SYMLINK_PATH="$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch/claude_monitor.py"

echo "=== Stopping Claude Code Command Center ==="

# 1. Kill server
if [ -f "$PIDFILE" ]; then
  PID=$(cat "$PIDFILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "[server] Stopped (PID $PID)"
  else
    echo "[server] Process $PID not running"
  fi
  rm "$PIDFILE"
else
  echo "[server] No PID file found"
fi

# 2. Remove iTerm2 symlink
if [ -L "$SYMLINK_PATH" ]; then
  rm "$SYMLINK_PATH"
  echo "[monitor] Removed iTerm2 AutoLaunch symlink"
else
  echo "[monitor] No symlink found"
fi

echo "Done."
```

- [ ] **Step 3: Make scripts executable**

Run: `chmod +x ~/iterm-dashboard/scripts/start.sh ~/iterm-dashboard/scripts/stop.sh`

- [ ] **Step 4: Commit**

```bash
cd ~/iterm-dashboard && git add scripts/ && git commit -m "feat: add start/stop scripts for backend and iTerm2 monitor"
```

---

### Task 11: Vite Config & Production Serving

**Files:**
- Modify: `dashboard/vite.config.ts`

- [ ] **Step 1: Update Vite config with proxy**

```typescript
// dashboard/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/ws": {
        target: "ws://localhost:7890",
        ws: true,
      },
      "/api": {
        target: "http://localhost:7890",
      },
    },
  },
});
```

- [ ] **Step 2: Build and verify**

Run: `cd ~/iterm-dashboard/dashboard && bun run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
cd ~/iterm-dashboard && git add dashboard/vite.config.ts && git commit -m "feat: configure Vite proxy for WebSocket and API endpoints"
```

---

### Task 12: Integration Test & End-to-End Verification

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""
Integration test: simulates monitor → backend → dashboard flow without iTerm2.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from server.main import app, state

import pytest

@pytest.fixture(autouse=True)
def reset_state():
    state.sessions.clear()
    state.queue.clear()
    state.full_outputs.clear()
    yield

def test_full_flow_monitor_to_dashboard():
    """Simulate: monitor sends event → dashboard receives it → user responds → command sent back."""
    client = TestClient(app)

    # Dashboard connects and gets empty snapshot
    with client.websocket_connect("/ws/dashboard") as dash:
        snap = dash.receive_json()
        assert snap["type"] == "snapshot"
        assert snap["sessions"] == {}

        # Monitor connects and sends a "ready" event
        with client.websocket_connect("/ws/monitor") as mon:
            mon.send_json({
                "session_id": "test-session",
                "tab_name": "feature-branch",
                "event_type": "ready",
                "tail_output": "Done! What would you like to do next?",
                "full_output": "Full history...\nDone! What would you like to do next?",
            })

            # Dashboard receives the event
            msg = dash.receive_json()
            assert msg["type"] == "event"
            assert msg["event"]["session_id"] == "test-session"
            assert msg["event"]["event_type"] == "ready"
            assert msg["queue_item"] is not None
            assert msg["queue_item"]["status"] == "pending"

            # User responds from dashboard
            dash.send_json({
                "command": "send_text",
                "session_id": "test-session",
                "payload": {"text": "Add unit tests"},
            })

            # Monitor receives the command
            cmd = mon.receive_json()
            assert cmd["command"] == "send_text"
            assert cmd["session_id"] == "test-session"
            assert cmd["payload"]["text"] == "Add unit tests"

def test_permission_prompt_flow():
    """Simulate: permission prompt → user clicks Allow."""
    client = TestClient(app)

    with client.websocket_connect("/ws/dashboard") as dash:
        dash.receive_json()  # snapshot

        with client.websocket_connect("/ws/monitor") as mon:
            mon.send_json({
                "session_id": "s2",
                "tab_name": "api-work",
                "event_type": "permission_prompt",
                "tail_output": "Read file package.json?\n\n  Allow  Deny",
                "full_output": "...\nRead file package.json?\n\n  Allow  Deny",
            })

            msg = dash.receive_json()
            assert msg["event"]["event_type"] == "permission_prompt"

            # User clicks Allow
            dash.send_json({
                "command": "send_text",
                "session_id": "s2",
                "payload": {"text": "y"},
            })

            cmd = mon.receive_json()
            assert cmd["payload"]["text"] == "y"

def test_rest_fallback_respond():
    """Test the REST endpoint for responding."""
    client = TestClient(app)

    # First create a session via the monitor flow
    with client.websocket_connect("/ws/monitor") as mon:
        mon.send_json({
            "session_id": "s3",
            "tab_name": "rest-test",
            "event_type": "ready",
            "tail_output": "Ready",
            "full_output": "Ready",
        })

    # Now respond via REST
    resp = client.post("/api/sessions/s3/respond", json={"text": "do the thing"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Queue item should be resolved
    pending = [q for q in state.queue if q.status == "pending"]
    assert len(pending) == 0
```

- [ ] **Step 2: Run integration tests**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/test_integration.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Run all tests**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/ -v`
Expected: All tests PASS (patterns + models + state + server + integration)

- [ ] **Step 4: Commit**

```bash
cd ~/iterm-dashboard && git add tests/test_integration.py && git commit -m "test: add integration tests for full monitor → dashboard → command flow"
```

---

### Task 13: Final Build & Smoke Test

- [ ] **Step 1: Build dashboard for production**

Run: `cd ~/iterm-dashboard/dashboard && bun run build`
Expected: Build succeeds, `dist/` directory created

- [ ] **Step 2: Start the server and verify**

Run: `cd ~/iterm-dashboard && source .venv/bin/activate && uvicorn server.main:app --host 127.0.0.1 --port 7890 &`

Run: `curl -s http://localhost:7890/api/sessions | python3 -m json.tool`
Expected: `{"sessions": {}, "queue": []}`

Run: `curl -s http://localhost:7890/ | head -5`
Expected: HTML content (the dashboard)

- [ ] **Step 3: Kill test server**

Run: `kill %1`

- [ ] **Step 4: Run full test suite one final time**

Run: `cd ~/iterm-dashboard && python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Final commit**

```bash
cd ~/iterm-dashboard && git add -A && git commit -m "chore: final build verification"
```
