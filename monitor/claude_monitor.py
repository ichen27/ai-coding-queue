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
POLL_INTERVAL = 2.0
IDLE_THRESHOLD = 3.0

_prev_content: dict[str, str] = {}
_prev_state: dict[str, str] = {}
_last_change_time: dict[str, float] = {}


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
                print(f"[monitor] History requested for {sid}: {len(lines)} lines")

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
                            contents = await session.async_get_contents()
                        except Exception:
                            continue

                        full_text = "\n".join(line.string for line in contents)

                        prev = _prev_content.get(sid, "")
                        if full_text != prev:
                            _prev_content[sid] = full_text
                            _last_change_time[sid] = now

                        state = detect_state(full_text)

                        time_since_change = now - _last_change_time.get(sid, now)
                        if state == "working" and time_since_change > IDLE_THRESHOLD:
                            state = "ready"

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
