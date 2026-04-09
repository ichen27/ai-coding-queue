#!/bin/bash
# scripts/stop.sh — Stop the Claude Code Command Center
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_PIDFILE="$DIR/.server.pid"
MONITOR_PIDFILE="$DIR/.monitor.pid"

echo "=== Stopping Claude Code Command Center ==="

# 1. Kill monitor
if [ -f "$MONITOR_PIDFILE" ]; then
  PID=$(cat "$MONITOR_PIDFILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "[monitor] Stopped (PID $PID)"
  else
    echo "[monitor] Process $PID not running"
  fi
  rm "$MONITOR_PIDFILE"
else
  echo "[monitor] No PID file found"
fi

# 2. Kill server
if [ -f "$SERVER_PIDFILE" ]; then
  PID=$(cat "$SERVER_PIDFILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "[server] Stopped (PID $PID)"
  else
    echo "[server] Process $PID not running"
  fi
  rm "$SERVER_PIDFILE"
else
  echo "[server] No PID file found"
fi

# 3. Clean up old AutoLaunch symlink if it exists
SYMLINK_PATH="$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch/claude_monitor.py"
if [ -L "$SYMLINK_PATH" ]; then
  rm "$SYMLINK_PATH"
fi

echo "Done."
