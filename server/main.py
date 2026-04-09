from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path

from server.state import StateManager
from server.models import MonitorEvent, Command

app = FastAPI(title="Claude Code Command Center")
state = StateManager()

monitor_ws: WebSocket | None = None
dashboard_clients: list[WebSocket] = []


class RespondRequest(BaseModel):
    text: str


async def broadcast_to_dashboards(message: dict):
    disconnected = []
    for ws in dashboard_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        dashboard_clients.remove(ws)


@app.websocket("/ws/monitor")
async def monitor_websocket(ws: WebSocket):
    global monitor_ws
    await ws.accept()
    monitor_ws = ws
    try:
        while True:
            data = await ws.receive_json()
            event = MonitorEvent(**data)
            queue_item = state.process_event(event)
            msg = {"type": "event", "event": event.model_dump()}
            if queue_item:
                msg["queue_item"] = queue_item.model_dump()
            await broadcast_to_dashboards(msg)
    except WebSocketDisconnect:
        monitor_ws = None


@app.websocket("/ws/dashboard")
async def dashboard_websocket(ws: WebSocket):
    await ws.accept()
    dashboard_clients.append(ws)
    await ws.send_json({"type": "snapshot", **state.get_snapshot()})
    try:
        while True:
            data = await ws.receive_json()
            command = Command(**data)
            if monitor_ws:
                await monitor_ws.send_json(command.model_dump())
            if command.command == "send_text":
                for item in state.queue:
                    if item.session_id == command.session_id and item.status == "pending":
                        item.status = "resolved"
                        break
                await broadcast_to_dashboards({
                    "type": "queue_update",
                    "queue": [q.model_dump() for q in state.queue],
                })
    except WebSocketDisconnect:
        if ws in dashboard_clients:
            dashboard_clients.remove(ws)


@app.get("/api/sessions")
async def get_sessions():
    return state.get_snapshot()


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    if session_id not in state.sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    return {"session_id": session_id, "output": state.get_full_output(session_id)}


@app.post("/api/sessions/{session_id}/respond")
async def respond_to_session(session_id: str, req: RespondRequest):
    if session_id not in state.sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    if monitor_ws:
        await monitor_ws.send_json({
            "command": "send_text",
            "session_id": session_id,
            "payload": {"text": req.text},
        })
    for item in state.queue:
        if item.session_id == session_id and item.status == "pending":
            item.status = "resolved"
            break
    return {"ok": True}


dashboard_dist = Path(__file__).parent.parent / "dashboard" / "dist"
if dashboard_dist.exists():
    app.mount("/assets", StaticFiles(directory=dashboard_dist / "assets"), name="assets")

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(dashboard_dist / "index.html")
