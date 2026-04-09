# AI Coding Queue

A localhost web dashboard that monitors multiple Claude Code sessions running in iTerm2 tabs. It queues notifications when sessions finish or need input, and lets you respond inline or jump directly to the tab.

Built for developers who run 10+ Claude Code sessions simultaneously and need a single place to manage them all.

## What It Does

When you're running many Claude Code sessions across iTerm2 tabs, there's no way to know which ones have finished, which need input, or which are waiting for tool approval — without manually clicking through each tab. AI Coding Queue solves this by:

- **Monitoring all iTerm2 tabs** for Claude Code activity in real-time
- **Detecting session states** — finished responses, questions, permission prompts (Allow/Deny)
- **Queuing notifications** in a web dashboard grouped by priority
- **Letting you respond inline** — type replies directly from the dashboard
- **Jumping to tabs** — one click to focus the iTerm2 tab for complex interactions

## Features

- **Real-time monitoring** — iTerm2 Python API polls all sessions every 2 seconds
- **Smart state detection** — pattern matching for Claude Code prompts, permission requests, questions, and idle states
- **Grouped dashboard** — sessions organized into "Needs Attention", "Working", and "Idle" sections
- **Inline responses** — reply to Claude Code directly from the dashboard
- **Quick actions** — one-click Allow/Deny for permission prompts
- **Jump to tab** — instantly focus the relevant iTerm2 tab and window
- **Expandable history** — view full session output without leaving the dashboard
- **Browser notifications** — get notified when sessions need attention
- **WebSocket live updates** — no polling, instant state changes
- **Dark theme** — GitHub-dark inspired UI

## Architecture

```
┌─────────────────┐     WebSocket      ┌─────────────────┐     WebSocket      ┌─────────────────┐
│  iTerm2 Monitor  │ ──────────────────▶│  Backend Server  │◀────────────────▶ │  Web Dashboard   │
│  (Python script) │                    │  (FastAPI)       │                    │  (React + Vite)  │
│                  │                    │                  │                    │                  │
│ Watches all      │                    │ Event queue      │                    │ Session cards    │
│ sessions via     │                    │ Session state    │                    │ Inline replies   │
│ iTerm2 API       │                    │ Command relay    │                    │ Quick actions    │
└─────────────────┘                    └─────────────────┘                    └─────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Monitor** | Python 3 + [iterm2](https://iterm2.com/python-api/) Python API |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) + WebSockets |
| **Dashboard** | [React](https://react.dev/) + TypeScript + [Vite](https://vite.dev/) |
| **Package Manager** | [Bun](https://bun.sh/) (frontend) |
| **Database** | None — all in-memory |

## Prerequisites

- **iTerm2** (macOS) with Python API enabled
- **Python 3.10+**
- **Bun** (for building the dashboard)
- **Claude Code** sessions running in iTerm2 tabs

## Getting Started

### 1. Clone and install

```bash
git clone https://github.com/ichen27/ai-coding-queue.git
cd ai-coding-queue

# Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
pip install iterm2

# Dashboard
cd dashboard && bun install && bun run build && cd ..
```

### 2. Start

```bash
./scripts/start.sh
```

This will:
- Start the FastAPI backend on `http://localhost:7890`
- Register the monitor script with iTerm2's AutoLaunch

### 3. Open the dashboard

Navigate to **http://localhost:7890** in your browser.

### 4. Stop

```bash
./scripts/stop.sh
```

## How It Works

1. The **iTerm2 monitor script** runs inside iTerm2's Python runtime and watches all sessions
2. Every 2 seconds, it reads each session's terminal buffer and runs pattern detection
3. When it detects a state change (Claude finished, needs input, permission prompt), it pushes an event to the backend via WebSocket
4. The **FastAPI backend** maintains session state and a notification queue, broadcasting updates to connected dashboards
5. The **React dashboard** displays sessions grouped by status with inline controls for responding
6. When you type a response or click Allow/Deny, the command flows back through the backend to the monitor, which sends the text to the correct iTerm2 session

## Development

### Run in dev mode

```bash
# Terminal 1: Backend
source .venv/bin/activate
uvicorn server.main:app --host 127.0.0.1 --port 7890 --reload

# Terminal 2: Dashboard (with hot reload)
cd dashboard && bun dev
```

The Vite dev server on port 5173 proxies `/ws` and `/api` requests to the backend on port 7890.

### Run tests

```bash
source .venv/bin/activate
python3 -m pytest tests/ -v
```

## License

MIT
