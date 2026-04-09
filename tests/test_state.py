import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.state import StateManager
from server.models import MonitorEvent

def test_process_event_creates_session():
    sm = StateManager()
    event = MonitorEvent(session_id="s1", tab_name="my-tab", event_type="working", tail_output="streaming...")
    sm.process_event(event)
    assert "s1" in sm.sessions
    assert sm.sessions["s1"].tab_name == "my-tab"
    assert sm.sessions["s1"].status == "working"

def test_process_event_updates_session():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="working", tail_output=""))
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    assert sm.sessions["s1"].status == "ready"
    assert sm.sessions["s1"].tail_output == "Done!"

def test_process_event_creates_queue_item_for_attention():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    assert len(sm.queue) == 1
    assert sm.queue[0].event_type == "ready"
    assert sm.queue[0].status == "pending"

def test_process_event_no_queue_for_working():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="working", tail_output=""))
    assert len(sm.queue) == 0

def test_process_event_resolves_old_queue_items():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    assert len(sm.queue) == 1
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="working", tail_output=""))
    assert sm.queue[0].status == "resolved"

def test_resolve_queue_item():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    item_id = sm.queue[0].id
    sm.resolve_queue_item(item_id)
    assert sm.queue[0].status == "resolved"

def test_get_grouped_sessions():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab1", event_type="ready", tail_output=""))
    sm.process_event(MonitorEvent(session_id="s2", tab_name="tab2", event_type="working", tail_output=""))
    sm.process_event(MonitorEvent(session_id="s3", tab_name="tab3", event_type="permission_prompt", tail_output=""))
    groups = sm.get_grouped_sessions()
    assert len(groups["attention"]) == 2
    assert len(groups["working"]) == 1
    assert len(groups["idle"]) == 0

def test_no_duplicate_queue_items():
    sm = StateManager()
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    sm.process_event(MonitorEvent(session_id="s1", tab_name="tab", event_type="ready", tail_output="Done!"))
    pending = [q for q in sm.queue if q.status == "pending"]
    assert len(pending) == 1
