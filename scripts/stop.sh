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
