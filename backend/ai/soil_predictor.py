"""Model lifecycle, context resolution, and asynchronous-safe inference service."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import pandas as pd
from fastapi.concurrency import run_in_threadpool
from fastapi import HTTPException
from pydantic import ValidationError

from .constants import DEFAULT_SOIL_TYPE
from .schemas import PredictionResult, SoilPredictionInput
from .storage import PREDICTIONS_FILE, append_record, load_field_configuration


LOGGER = logging.getLogger(__name__)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "model" / "soil_moisture_model.joblib"


def load_model_pipeline() -> Any | None:
    """Load the one bundled pipeline once during app lifespan, or return ``None`` safely."""
    configured_path = os.getenv("SOIL_MOISTURE_MODEL_PATH", "").strip()
    model_path = Path(configured_path) if configured_path else DEFAULT_MODEL_PATH
    try:
        model = joblib.load(model_path)
        LOGGER.info("Soil-moisture model loaded from %s", model_path)
        return model
    except Exception as exc:
        LOGGER.error("Soil-moisture model unavailable at %s: %s", model_path, exc)
        return None


def resolve_active_field_context(app: Any) -> Optional[Dict[str, Any]]:
    """Resolve field context in mandatory order: active mission, active field, then no context."""
    active_mission = getattr(app.state, "active_mission", None)
    field_id = active_mission.get("field_id") if active_mission else getattr(app.state, "active_field_id", None)
    if not field_id:
        return None
    configuration = load_field_configuration(field_id) or {}
    return {"field_id": field_id, "soil_type": configuration.get("soil_type"),
            "last_irrigation_timestamp": configuration.get("last_irrigation_timestamp")}


def resolve_soil_type(raw_soil_type: Any, field_id: str) -> str:
    """Normalize configured/raw soil type, warning once per invalid lookup and using loam safely."""
    from .constants import SUPPORTED_SOIL_TYPES
    if not isinstance(raw_soil_type, str) or raw_soil_type not in SUPPORTED_SOIL_TYPES:
        LOGGER.warning("Unknown soil_type '%s' for field '%s'; falling back to '%s'", raw_soil_type, field_id, DEFAULT_SOIL_TYPE)
        return DEFAULT_SOIL_TYPE
    return raw_soil_type


def hours_since_irrigation(last_irrigation_timestamp: Optional[str], now: datetime) -> float:
    """Compute non-negative fractional hours since irrigation; malformed/future times safely become zero."""
    if not last_irrigation_timestamp:
        return 0.0
    try:
        irrigation_time = datetime.fromisoformat(last_irrigation_timestamp.replace("Z", "+00:00"))
        if irrigation_time.tzinfo is None:
            irrigation_time = irrigation_time.replace(tzinfo=timezone.utc)
        value = (now - irrigation_time).total_seconds() / 3600.0
        if value < 0:
            LOGGER.warning("Future irrigation timestamp for field context; clamping hours_since_irrigation to 0.0")
            return 0.0
        return value
    except (TypeError, ValueError):
        LOGGER.warning("Invalid irrigation timestamp for field context; defaulting hours_since_irrigation to 0.0")
        return 0.0


async def predict_soil_moisture(app: Any, model_input: SoilPredictionInput, field_id: Optional[str] = None) -> Optional[PredictionResult]:
    """Run one clipped Random Forest inference off the event loop and persist its distinct ML record."""
    if getattr(app.state, "ai_status", "AI_UNAVAILABLE") == "AI_UNAVAILABLE" or getattr(app.state, "ml_model", None) is None:
        raise HTTPException(status_code=503, detail={"status": "AI_UNAVAILABLE", "message": "Soil-moisture model is unavailable"})
    context = {"field_id": field_id} if field_id else resolve_active_field_context(app)
    if not context or not context.get("field_id"):
        LOGGER.info("AI prediction skipped: no active field/mission context")
        return None
    try:
        feature_frame = pd.DataFrame([model_input.model_dump()], columns=["x_m", "y_m", "soil_type", "humidity_pct", "depth_mm", "hours_since_irrigation"])
        value = await run_in_threadpool(app.state.ml_model.predict, feature_frame)
        predicted = max(0.0, min(100.0, float(value[0])))  # Physical scale boundary, never a sensor replacement.
    except Exception as exc:
        LOGGER.error("AI inference failed for field %s with x=%s y=%s: %s", context["field_id"], model_input.x_m, model_input.y_m, exc)
        return None
    result = PredictionResult(timestamp=datetime.now(timezone.utc), field_id=context["field_id"],
                              x_m=model_input.x_m, y_m=model_input.y_m, depth_mm=model_input.depth_mm,
                              soil_type=model_input.soil_type, humidity_pct=model_input.humidity_pct,
                              hours_since_irrigation=model_input.hours_since_irrigation,
                              predicted_moisture_pct=predicted)
    record = result.model_dump(mode="json")
    record["timestamp"] = result.timestamp.isoformat().replace("+00:00", "Z")
    append_record(PREDICTIONS_FILE, record)
    return result


async def prediction_from_sensor_telemetry(app: Any, payload: Dict[str, Any]) -> Optional[PredictionResult]:
    """Resolve telemetry context and invoke canonical inference only for valid SENSOR payloads."""
    # Infinite-loop guard: ML records never enter a prediction-producing code path.
    if payload.get("source") != "SENSOR":
        return None
    context = resolve_active_field_context(app)
    if context is None:
        LOGGER.info("AI prediction skipped: no active field/mission context")
        return None
    now = datetime.now(timezone.utc)
    soil_type = resolve_soil_type(payload.get("soil_type", context.get("soil_type")), context["field_id"])
    try:
        model_input = SoilPredictionInput(x_m=payload["x_m"], y_m=payload["y_m"], soil_type=soil_type,
            humidity_pct=payload["humidity_pct"], depth_mm=payload["depth_mm"],
            hours_since_irrigation=hours_since_irrigation(context.get("last_irrigation_timestamp"), now))
    except (KeyError, ValidationError) as exc:
        LOGGER.info("AI prediction skipped: invalid sensor telemetry (%s)", exc)
        return None
    return await predict_soil_moisture(app, model_input, field_id=context["field_id"])
