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
    with client.websocket_connect("/ws/dashboard") as dash_ws:
        snapshot = dash_ws.receive_json()
        assert snapshot["type"] == "snapshot"
        with client.websocket_connect("/ws/monitor") as mon_ws:
            mon_ws.send_json({
                "session_id": "s1",
                "tab_name": "test-tab",
                "event_type": "ready",
                "tail_output": "Done!",
                "full_output": "Full history",
            })
            data = dash_ws.receive_json()
            assert data["type"] == "event"
            assert data["event"]["session_id"] == "s1"
