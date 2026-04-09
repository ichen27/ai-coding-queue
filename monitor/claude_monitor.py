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

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from patterns import detect_state, clean_output, strip_chrome, is_claude_code_session

SERVER_URL = "ws://localhost:7890/ws/monitor"
POLL_INTERVAL = 2.0

_prev_content: dict[str, str] = {}
_prev_state: dict[str, str] = {}
_last_change_time: dict[str, float] = {}

NUM_LINES_TO_READ = 200  # Read last N lines from each session


async def read_session_contents(session) -> str:
    """Read terminal contents from a session using the iTerm2 API."""
    line_info = await session.async_get_line_info()
    overflow = line_info.overflow
    total = line_info.mutable_area_height + line_info.scrollback_buffer_height
    first_line = max(overflow, total - NUM_LINES_TO_READ + overflow)
    num_lines = min(NUM_LINES_TO_READ, total - (first_line - overflow))
    if num_lines <= 0:
        return ""
    contents = await session.async_get_contents(first_line, num_lines)
    # Respect soft-wrap: only insert \n at hard newlines, use space at soft wraps
    parts = []
    for i, line in enumerate(contents):
        text = line.string.rstrip()
        parts.append(text)
        if i < len(contents) - 1:
            # hard_newline=False means line is soft-wrapped continuation
            if line.hard_eol:
                parts.append("\n")
            else:
                # Add space at soft-wrap boundary to preserve word spacing
                if text and not text.endswith(" "):
                    parts.append(" ")
    return "".join(parts)


async def connect_to_server():
    while True:
        try:
            ws = await websockets.connect(SERVER_URL)
            print(f"[monitor] Connected to {SERVER_URL}")
            return ws
        except Exception as e:
            print(f"[monitor] Connection failed ({e}), retrying in 3s...")
            await asyncio.sleep(3)


async def handle_commands(ws, app):
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
                await session.async_send_text(text + "\r")
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
                full_text = await read_session_contents(session)
                print(f"[monitor] History requested for {sid}: {len(full_text.split(chr(10)))} lines")

    except websockets.ConnectionClosed:
        print("[monitor] Server connection lost in command handler")


async def poll_sessions(ws, app):
    while True:
        try:
            now = asyncio.get_event_loop().time()

            for window in app.terminal_windows:
                for tab in window.tabs:
                    tab_name = await tab.async_get_variable("titleOverride") or tab.tab_id
                    for session in tab.sessions:
                        sid = session.session_id

                        try:
                            full_text = await read_session_contents(session)
                        except Exception:
                            continue

                        if not is_claude_code_session(full_text):
                            # Not a Claude Code session — skip
                            if sid in _prev_state:
                                del _prev_state[sid]
                            continue

                        prev = _prev_content.get(sid, "")
                        content_changed = full_text != prev
                        if content_changed:
                            _prev_content[sid] = full_text
                            _last_change_time[sid] = now

                        state = detect_state(full_text, content_changed=content_changed)

                        prev_state = _prev_state.get(sid)
                        state_changed = state != prev_state
                        if state_changed:
                            _prev_state[sid] = state

                        # Send update on state change OR content change
                        if state_changed or content_changed:
                            cleaned = clean_output(full_text)
                            stripped = strip_chrome(cleaned)
                            event = {
                                "session_id": sid,
                                "tab_name": str(tab_name),
                                "event_type": state,
                                "tail_output": stripped,
                                "summary": "",
                                "full_output": cleaned,
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

        poll_task = asyncio.create_task(poll_sessions(ws, app))
        cmd_task = asyncio.create_task(handle_commands(ws, app))

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
