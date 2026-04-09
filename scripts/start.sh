#!/bin/bash
# scripts/start.sh — Start the Claude Code Command Center
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_PIDFILE="$DIR/.server.pid"
MONITOR_PIDFILE="$DIR/.monitor.pid"

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
echo $! > "$SERVER_PIDFILE"
echo "[server] PID: $(cat "$SERVER_PIDFILE")"

# 3. Wait for server to be ready
echo "[server] Waiting for backend..."
for i in $(seq 1 10); do
  if curl -s http://localhost:7890/api/sessions > /dev/null 2>&1; then
    echo "[server] Ready."
    break
  fi
  sleep 0.5
done

# 4. Start monitor as a background process (using our venv's Python)
echo "[monitor] Starting iTerm2 monitor..."
cd "$DIR"
python3 monitor/claude_monitor.py > "$DIR/.monitor.log" 2>&1 &
echo $! > "$MONITOR_PIDFILE"
echo "[monitor] PID: $(cat "$MONITOR_PIDFILE")"

echo ""
echo "Dashboard: http://localhost:7890"
echo "Monitor log: $DIR/.monitor.log"
echo "To stop:     ./scripts/stop.sh"
