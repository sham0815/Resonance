"""FastAPI service bridging the dashboard, mission planner, and ESP32."""

import json
import logging
import math
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from path_planner import ConvexHullPlanner
from ai.soil_predictor import (load_model_pipeline, prediction_from_sensor_telemetry,
                               resolve_active_field_context, resolve_soil_type)
from ai.schemas import SoilPredictionInput
from ai.storage import SENSOR_FILE, append_record, save_field_configuration

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Load the ML pipeline once without making rover startup depend on AI availability."""
    application.state.ml_model = load_model_pipeline()
    application.state.ai_status = "AI_AVAILABLE" if application.state.ml_model is not None else "AI_UNAVAILABLE"
    application.state.active_mission = None
    application.state.active_field_id = None
    yield


app = FastAPI(title="AgriRover Mission Planner", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

esp32_ws: Optional[WebSocket] = None
frontend_ws: Optional[WebSocket] = None


class FieldBoundary(BaseModel):
    field_id: str = Field(min_length=1)
    boundary_points: List[Dict[str, float]]
    row_spacing_m: float = Field(default=1.0, gt=0)
    sampling_density_m: float = Field(default=3.0, gt=0)
    active_payload: str = "IRRIGATION"
    prescription: Dict[str, Any] = Field(default_factory=dict)
    soil_type: Optional[str] = None


def build_mission(boundary: FieldBoundary) -> Dict[str, Any]:
    return ConvexHullPlanner(boundary.row_spacing_m, boundary.sampling_density_m).generate_grid(boundary.boundary_points, field_id=boundary.field_id)


def _configure_field(boundary: FieldBoundary) -> None:
    """Persist the field configuration that is the AI pipeline's soil-type source of truth."""
    soil_type = resolve_soil_type(boundary.soil_type, boundary.field_id)
    save_field_configuration(boundary.field_id, {"soil_type": soil_type})
    app.state.active_field_id = boundary.field_id


async def _ingest_telemetry(payload: Dict[str, Any]) -> None:
    """Persist raw SENSOR readings and schedule best-effort ML work without delaying telemetry relay."""
    # Mandatory infinite-loop guard: predictions are never treated as new physical measurements.
    if payload.get("source") != "SENSOR":
        return
    record = dict(payload)
    record["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    append_record(SENSOR_FILE, record)
    if app.state.ai_status != "AI_UNAVAILABLE":
        # Do not await here: one slow model evaluation cannot serialize websocket telemetry.
        import asyncio
        asyncio.create_task(_publish_sensor_prediction(payload))


async def _publish_sensor_prediction(payload: Dict[str, Any]) -> None:
    """Store/publish ML output on its own AI topic, never through telemetry ingestion."""
    try:
        result = await prediction_from_sensor_telemetry(app, payload)
        if result is not None:
            await _send_to_frontend({"type": "AI_SOIL_MOISTURE_PREDICTION", "payload": result.model_dump(mode="json")})
    except Exception as exc:
        # This is a final isolation barrier; raw telemetry has already been persisted and relayed.
        LOGGER.error("AI prediction task failed without affecting telemetry: %s", exc)


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    return {"status": "ok", "timestamp": time.time(), "esp32_connected": esp32_ws is not None,
            "ai_status": getattr(app.state, "ai_status", "AI_UNAVAILABLE")}


@app.post("/api/generate-mission")
async def generate_mission(boundary: FieldBoundary) -> Dict[str, Any]:
    """REST mission generation works whether or not a rover is connected."""
    try:
        _configure_field(boundary)
        return {"status": "success", "mission_plan": build_mission(boundary)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}


@app.post("/ai/predict-soil-moisture")
async def manual_soil_prediction(request: SoilPredictionInput) -> Dict[str, Any]:
    """Run the canonical ML inference for the active persisted field configuration."""
    if getattr(app.state, "ai_status", "AI_UNAVAILABLE") == "AI_UNAVAILABLE":
        raise HTTPException(status_code=503, detail={"status": "AI_UNAVAILABLE", "message": "Soil-moisture model is unavailable"})
    context = resolve_active_field_context(app)
    if context is None:
        LOGGER.info("AI prediction skipped: no active field/mission context")
        raise HTTPException(status_code=409, detail="No active field/mission context")
    # Configuration, not a caller's ad-hoc value, is the authoritative soil type for an active field.
    resolved_input = request.model_copy(update={"soil_type": resolve_soil_type(context.get("soil_type"), context["field_id"])})
    from ai.soil_predictor import predict_soil_moisture
    result = await predict_soil_moisture(app, resolved_input, field_id=context["field_id"])
    if result is None:
        raise HTTPException(status_code=409, detail="AI prediction skipped")
    return result.model_dump(mode="json")


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
                telemetry = payload.get("payload", {})
                if isinstance(telemetry, dict):
                    await _ingest_telemetry(telemetry)
                await _send_to_frontend({"type": "TELEMETRY", "payload": telemetry})
            elif isinstance(payload, dict):
                await _ingest_telemetry(payload)
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
                app.state.active_mission = None
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
        boundary = FieldBoundary(**payload)
        _configure_field(boundary)
        app.state.active_mission = {"field_id": boundary.field_id}
        plan = build_mission(boundary)
        await websocket.send_text(json.dumps({"type": "MISSION_STARTED", "plan": plan}))
        await _send_mission_to_esp32(plan)
    except (TypeError, ValueError) as exc:
        await websocket.send_text(json.dumps({"type": "MISSION_ERROR", "error": str(exc)}))
    except Exception:
        await websocket.send_text(json.dumps({"type": "MISSION_ERROR", "error": "Internal server error"}))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
