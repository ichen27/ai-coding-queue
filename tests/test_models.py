import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.models import SessionState, QueueItem, MonitorEvent, Command
import time

def test_session_state_creation():
    s = SessionState(
        session_id="abc-123",
        tab_name="deer-flow",
        status="working",
        tail_output="",
        last_event_time=time.time(),
    )
    assert s.session_id == "abc-123"
    assert s.status == "working"

def test_queue_item_creation():
    q = QueueItem(
        session_id="abc-123",
        event_type="ready",
        tail_output="Done!",
    )
    assert q.id
    assert q.status == "pending"
    assert q.created_at > 0

def test_monitor_event_creation():
    e = MonitorEvent(
        session_id="abc-123",
        tab_name="deer-flow",
        event_type="ready",
        tail_output="Done!",
        full_output="Full history here",
    )
    assert e.timestamp > 0

def test_command_creation():
    c = Command(
        command="send_text",
        session_id="abc-123",
        payload={"text": "yes"},
    )
    assert c.command == "send_text"
