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
