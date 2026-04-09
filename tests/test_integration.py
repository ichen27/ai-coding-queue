"""
Integration test: simulates monitor → backend → dashboard flow without iTerm2.

Uses uvicorn in a background thread with real WebSocket clients so all connections
share the same asyncio event loop, enabling proper cross-connection messaging.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import threading
import time
import pytest
import uvicorn
import websockets

import server.main as main_module
from server.main import app, state
from fastapi.testclient import TestClient

# ── Shared server fixture ──────────────────────────────────────────────────────

_SERVER_HOST = "127.0.0.1"
_SERVER_PORT = 18765
_BASE_WS = f"ws://{_SERVER_HOST}:{_SERVER_PORT}"
_BASE_HTTP = f"http://{_SERVER_HOST}:{_SERVER_PORT}"


@pytest.fixture(scope="module")
def live_server():
    """Start uvicorn in a background thread once for all integration tests."""
    config = uvicorn.Config(app, host=_SERVER_HOST, port=_SERVER_PORT, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to start
    for _ in range(50):
        try:
            import socket
            s = socket.create_connection((_SERVER_HOST, _SERVER_PORT), timeout=0.1)
            s.close()
            break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)

    yield

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def reset_state(live_server):
    state.sessions.clear()
    state.queue.clear()
    state.full_outputs.clear()
    main_module.monitor_ws = None
    main_module.dashboard_clients.clear()
    yield


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_full_flow_monitor_to_dashboard():
    """
    Simulates the full monitor → backend → dashboard → command flow.
    """
    async def _test():
        async with websockets.connect(f"{_BASE_WS}/ws/dashboard") as dash:
            raw = await asyncio.wait_for(dash.recv(), timeout=5)
            import json
            snap = json.loads(raw)
            assert snap["type"] == "snapshot"
            assert snap["sessions"] == {}

            async with websockets.connect(f"{_BASE_WS}/ws/monitor") as mon:
                await mon.send(json.dumps({
                    "session_id": "test-session",
                    "tab_name": "feature-branch",
                    "event_type": "ready",
                    "tail_output": "Done! What would you like to do next?",
                    "full_output": "Full history...\nDone! What would you like to do next?",
                }))

                raw = await asyncio.wait_for(dash.recv(), timeout=5)
                msg = json.loads(raw)
                assert msg["type"] == "event"
                assert msg["event"]["session_id"] == "test-session"
                assert msg["event"]["event_type"] == "ready"
                assert msg["queue_item"] is not None
                assert msg["queue_item"]["status"] == "pending"

                await dash.send(json.dumps({
                    "command": "send_text",
                    "session_id": "test-session",
                    "payload": {"text": "Add unit tests"},
                }))

                raw = await asyncio.wait_for(mon.recv(), timeout=5)
                cmd = json.loads(raw)
                assert cmd["command"] == "send_text"
                assert cmd["session_id"] == "test-session"
                assert cmd["payload"]["text"] == "Add unit tests"

                # Consume queue_update
                raw = await asyncio.wait_for(dash.recv(), timeout=5)
                queue_update = json.loads(raw)
                assert queue_update["type"] == "queue_update"

    asyncio.run(_test())


def test_permission_prompt_flow():
    """
    Simulates a permission_prompt event and confirming with 'y'.
    """
    import json

    async def _test():
        async with websockets.connect(f"{_BASE_WS}/ws/dashboard") as dash:
            await asyncio.wait_for(dash.recv(), timeout=5)  # snapshot

            async with websockets.connect(f"{_BASE_WS}/ws/monitor") as mon:
                await mon.send(json.dumps({
                    "session_id": "s2",
                    "tab_name": "api-work",
                    "event_type": "permission_prompt",
                    "tail_output": "Read file package.json?\n\n  Allow  Deny",
                    "full_output": "...\nRead file package.json?\n\n  Allow  Deny",
                }))

                raw = await asyncio.wait_for(dash.recv(), timeout=5)
                msg = json.loads(raw)
                assert msg["event"]["event_type"] == "permission_prompt"

                await dash.send(json.dumps({
                    "command": "send_text",
                    "session_id": "s2",
                    "payload": {"text": "y"},
                }))

                raw = await asyncio.wait_for(mon.recv(), timeout=5)
                cmd = json.loads(raw)
                assert cmd["payload"]["text"] == "y"

                # Consume queue_update
                raw = await asyncio.wait_for(dash.recv(), timeout=5)
                queue_update = json.loads(raw)
                assert queue_update["type"] == "queue_update"

    asyncio.run(_test())


def test_rest_fallback_respond():
    """
    Simulates the REST /respond endpoint as a fallback when no dashboard is connected.
    """
    import json

    async def _test():
        async with websockets.connect(f"{_BASE_WS}/ws/monitor") as mon:
            await mon.send(json.dumps({
                "session_id": "s3",
                "tab_name": "rest-test",
                "event_type": "ready",
                "tail_output": "Ready",
                "full_output": "Ready",
            }))
            # Give server time to process the event
            await asyncio.sleep(0.1)

    asyncio.run(_test())

    import httpx
    resp = httpx.post(f"{_BASE_HTTP}/api/sessions/s3/respond", json={"text": "do the thing"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    pending = [q for q in state.queue if q.status == "pending"]
    assert len(pending) == 0
