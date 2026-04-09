# Claude Code Command Center — Design Spec

## Problem

When running 10+ Claude Code sessions across iTerm2 tabs, there's no way to know which sessions have finished, which need input, or which are waiting for tool approval — without manually checking each tab.

## Solution

A localhost web dashboard that monitors all iTerm2 tabs running Claude Code, queues notifications when sessions finish or need input, and lets you respond inline or jump to the tab.

## Architecture

Three components in a pipeline:

```
iTerm2 Monitor (Python) → Backend Server (FastAPI) → Web Dashboard (React)
         ↑                        ↓
         └────── commands ────────┘
```

### Component 1: iTerm2 Monitor

**Location:** `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/claude_monitor.py` (symlinked from project)

**Responsibilities:**
- Watch all iTerm2 sessions for Claude Code output patterns
- Push events to backend via WebSocket (`ws://localhost:7890/ws/monitor`)
- Receive commands from backend (send text, focus tab, get history)

**Detection patterns:**

| Pattern | Event Type | Priority |
|---------|-----------|----------|
| Claude Code input prompt (❯ or $ after output ends) | `ready` | Normal |
| Permission prompt (Allow/Deny) | `permission_prompt` | High |
| Question with ? after Claude output | `needs_input` | High |
| Output idle > 3s after streaming | `ready` (fallback) | Low |

**Event payload:**

```json
{
  "session_id": "uuid",
  "tab_name": "string",
  "event_type": "ready | needs_input | permission_prompt",
  "tail_output": "last ~50 lines",
  "full_output": "entire buffer",
  "timestamp": 1712678400
}
```

**Inbound commands:**
- `send_text(session_id, text)` — calls `session.async_send_text(text + "\n")`
- `focus_tab(session_id)` — calls `session.async_activate()` + window activate
- `get_history(session_id)` — returns `session.async_get_contents()`

### Component 2: Backend Server (FastAPI)

**Port:** 7890

**Endpoints:**
- `WS /ws/monitor` — iTerm2 monitor connection (push events, receive commands)
- `WS /ws/dashboard` — Dashboard connection (receive events, send commands)
- `GET /api/sessions` — All active sessions and their state
- `GET /api/sessions/{id}/history` — Full output for a session
- `POST /api/sessions/{id}/respond` — Send text (REST fallback)

**In-memory state:**
- `sessions: dict[str, SessionState]` — status, last output, tab name per session
- `queue: list[QueueItem]` — items needing attention, ordered newest first
- Queue item states: `pending` → `seen` → `resolved`
- Responding auto-resolves the item
- No database. State rebuilds from monitor heartbeat on restart.

**SessionState model:**
```python
class SessionState:
    session_id: str
    tab_name: str
    status: "working" | "ready" | "needs_input" | "permission_prompt" | "idle"
    tail_output: str
    last_event_time: float
```

**QueueItem model:**
```python
class QueueItem:
    id: str
    session_id: str
    event_type: str
    tail_output: str
    status: "pending" | "seen" | "resolved"
    created_at: float
```

### Component 3: Web Dashboard (React + Vite)

**URL:** `http://localhost:7890` (served by FastAPI as static files in production, Vite dev server in dev)

**Layout:**
- Sessions grouped into three sections: Needs Attention → Working → Idle
- Each session is a card showing tab name, status, and tail output

**Session card features:**
- Permission prompts: quick-action Allow/Deny buttons
- Ready/needs_input: inline text input for responding
- "Show history" toggle: expands to scrollable full output
- "Jump to Tab" button: focuses the iTerm2 tab
- Visual priority: red for permission prompts, yellow for questions, green for ready

**Global features:**
- WebSocket connection status indicator
- Browser notifications for new queue items
- Session count badges per group
- Auto-scroll to newest attention item

## Project Structure

```
~/iterm-dashboard/
├── monitor/
│   ├── claude_monitor.py         # iTerm2 AutoLaunch script
│   └── patterns.py               # Claude Code output pattern matchers
├── server/
│   ├── main.py                   # FastAPI app + WebSocket handlers
│   ├── models.py                 # Pydantic models
│   ├── state.py                  # In-memory state manager
│   └── requirements.txt          # fastapi, uvicorn, websockets
├── dashboard/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── SessionCard.tsx
│   │   │   ├── QueueList.tsx
│   │   │   ├── HistoryPanel.tsx
│   │   │   └── StatusBar.tsx
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts
│   │   └── types.ts
│   ├── package.json
│   └── vite.config.ts
├── scripts/
│   ├── start.sh
│   └── stop.sh
└── README.md
```

## Startup & Lifecycle

1. `./scripts/start.sh`:
   - Starts FastAPI server on localhost:7890
   - Symlinks monitor script into iTerm2 AutoLaunch directory
   - If iTerm2 is running, triggers the script
2. Monitor connects to backend WebSocket, begins watching sessions
3. User opens http://localhost:7890
4. `./scripts/stop.sh`: kills server, removes AutoLaunch symlink

## Tech Stack

- **Monitor:** Python 3.14 + iterm2 package
- **Backend:** FastAPI + uvicorn + websockets
- **Dashboard:** React + TypeScript + Vite, bundled with Bun
- **No database, no external services**

## Non-goals

- Full terminal emulation in the dashboard (we show text, not rendered terminal)
- Supporting non-iTerm2 terminals
- Persisting history across server restarts
- Authentication (localhost only)
