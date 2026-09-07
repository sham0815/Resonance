"""FastAPI service bridging the dashboard, mission planner, and ESP32."""

import json
import math
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from path_planner import ConvexHullPlanner

app = FastAPI(title="AgriRover Mission Planner")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

esp32_ws: Optional[WebSocket] = None
frontend_ws: Optional[WebSocket] = None


class FieldBoundary(BaseModel):
    field_id: str = Field(min_length=1)
    boundary_points: List[Dict[str, float]]
    row_spacing_m: float = 1.0
    sampling_density_m: float = 3.0
    active_payload: str = "IRRIGATION"
    prescription: Dict[str, Any] = Field(default_factory=dict)


def build_mission(boundary: FieldBoundary) -> Dict[str, Any]:
    return ConvexHullPlanner(boundary.row_spacing_m, boundary.sampling_density_m).generate_grid(boundary.boundary_points, field_id=boundary.field_id)


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    return {"status": "ok", "timestamp": time.time(), "esp32_connected": esp32_ws is not None}


@app.post("/api/generate-mission")
async def generate_mission(boundary: FieldBoundary) -> Dict[str, Any]:
    """REST mission generation works whether or not a rover is connected."""
    try:
        return {"status": "success", "mission_plan": build_mission(boundary)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}


async def _send_to_frontend(message: Dict[str, Any]) -> None:
    global frontend_ws
    if frontend_ws is None:
        return
    try:
        await frontend_ws.send_text(json.dumps(message))
    except Exception:
        frontend_ws = None


async def _send_mission_to_esp32(plan: Dict[str, Any]) -> None:
    """Send logical waypoint commands only; physical implementation stays in firmware."""
    global esp32_ws
    if esp32_ws is None:
        return
    try:
        for cmd_id, local_point in enumerate(plan["waypoints_local"]):
            heading = 0.0
            if cmd_id + 1 < len(plan["waypoints_local"]):
                next_point = plan["waypoints_local"][cmd_id + 1]
                heading = math.degrees(math.atan2(next_point[1] - local_point[1], next_point[0] - local_point[0]))
            await esp32_ws.send_text(json.dumps({"cmd_id": cmd_id, "type": "WAYPOINT", "target_x_m": local_point[0], "target_y_m": local_point[1], "heading_deg": heading, "action": "NAVIGATE", "payload_param": 0, "timeout_ms": 30000}))
        for sample_id, sample_point in enumerate(plan["sampling_points"], start=len(plan["waypoints_local"])):
            await esp32_ws.send_text(json.dumps({"cmd_id": sample_id, "type": "WAYPOINT", "target_x_m": sample_point[0], "target_y_m": sample_point[1], "heading_deg": 0.0, "action": "SAMPLE_SOIL", "payload_param": 0, "timeout_ms": 30000}))
    except Exception:
        esp32_ws = None


@app.websocket("/ws/esp32")
async def esp32_endpoint(websocket: WebSocket) -> None:
    global esp32_ws
    await websocket.accept()
    esp32_ws = websocket
    try:
        while True:
            try:
                payload = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("type") == "TELEMETRY":
                await _send_to_frontend({"type": "TELEMETRY", "payload": payload.get("payload", {})})
            elif isinstance(payload, dict):
                await _send_to_frontend({"type": "TELEMETRY", "payload": payload})
    except WebSocketDisconnect:
        pass
    finally:
        if esp32_ws is websocket:
            esp32_ws = None


@app.websocket("/ws/frontend")
async def frontend_endpoint(websocket: WebSocket) -> None:
    global frontend_ws
    await websocket.accept()
    frontend_ws = websocket
    try:
        while True:
            try:
                message = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "MISSION_ERROR", "error": "Invalid JSON message"}))
                continue
            if not isinstance(message, dict):
                await websocket.send_text(json.dumps({"type": "MISSION_ERROR", "error": "Message must be an object"}))
            elif message.get("type") == "START_MISSION":
                await _handle_start_mission(websocket, message.get("payload", {}))
            elif message.get("type") == "STOP_MISSION":
                if esp32_ws is not None:
                    try:
                        await esp32_ws.send_text(json.dumps({"type": "STOP_MISSION"}))
                    except Exception:
                        pass
                await websocket.send_text(json.dumps({"type": "MISSION_STOPPED", "message": "Mission halted by user"}))
            else:
                await websocket.send_text(json.dumps({"type": "MISSION_ERROR", "error": "Unknown message type"}))
    except WebSocketDisconnect:
        pass
    finally:
        if frontend_ws is websocket:
            frontend_ws = None


async def _handle_start_mission(websocket: WebSocket, payload: Dict[str, Any]) -> None:
    try:
        plan = build_mission(FieldBoundary(**payload))
        await websocket.send_text(json.dumps({"type": "MISSION_STARTED", "plan": plan}))
        await _send_mission_to_esp32(plan)
    except (TypeError, ValueError) as exc:
        await websocket.send_text(json.dumps({"type": "MISSION_ERROR", "error": str(exc)}))
    except Exception:
        await websocket.send_text(json.dumps({"type": "MISSION_ERROR", "error": "Internal server error"}))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
