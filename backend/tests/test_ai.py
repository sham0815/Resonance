"""Regression tests for the isolated, non-recursive soil-moisture AI pipeline."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
from fastapi.testclient import TestClient

from ai.constants import DEFAULT_SOIL_TYPE, SUPPORTED_SOIL_TYPES
from ai.schemas import PredictionResult
from ai.soil_predictor import predict_soil_moisture, prediction_from_sensor_telemetry, resolve_active_field_context, resolve_soil_type
from ai.storage import save_field_configuration
from main import app


VALID_SENSOR = {"source": "SENSOR", "x_m": 4.5, "y_m": 12.0, "humidity_pct": 68.2, "depth_mm": 150.0}


def test_synthetic_dataset_is_complete_and_balanced():
    """The committed reproducible dataset has all supported types and bounded targets."""
    dataset = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "synthetic" / "soil_moisture_dataset.csv")
    assert len(dataset) >= 2000
    assert set(dataset["soil_type"]) == set(SUPPORTED_SOIL_TYPES)
    assert not dataset.isna().any().any()
    assert dataset["soil_moisture_pct"].between(0, 100).all()


def test_telemetry_guard_prevents_prediction_recursion():
    """ML_MODEL telemetry is ignored, while a complete SENSOR reading invokes inference once."""
    app.state.active_mission = {"field_id": "guard-field"}
    save_field_configuration("guard-field", {"soil_type": "loam"})
    with patch("ai.soil_predictor.predict_soil_moisture", new_callable=AsyncMock, return_value=None) as predict:
        asyncio.run(prediction_from_sensor_telemetry(app, {**VALID_SENSOR, "source": "ML_MODEL"}))
        assert predict.await_count == 0
        asyncio.run(prediction_from_sensor_telemetry(app, VALID_SENSOR))
        assert predict.await_count == 1


def test_context_resolution_prefers_mission_then_field_then_skip():
    """Context precedence matches the documented active-mission → active-field order."""
    save_field_configuration("configured-field", {"soil_type": "silt"})
    app.state.active_field_id = "configured-field"
    app.state.active_mission = {"field_id": "mission-field"}
    assert resolve_active_field_context(app)["field_id"] == "mission-field"
    app.state.active_mission = None
    assert resolve_active_field_context(app)["field_id"] == "configured-field"
    app.state.active_field_id = None
    assert resolve_active_field_context(app) is None


def test_unknown_soil_type_falls_back_safely(caplog):
    """Unknown field values retain operation using the one central loam default."""
    assert resolve_soil_type("volcanic", "field-x") == DEFAULT_SOIL_TYPE
    assert "Unknown soil_type 'volcanic' for field 'field-x'" in caplog.text


def test_api_rejects_invalid_input_with_422_and_runs_model_for_active_field():
    """Strict direct API validation prevents invalid inputs from reaching the model."""
    mission = {"field_id": "api-field", "boundary_points": [{"lat": 13.08, "lng": 80.27}, {"lat": 13.0801, "lng": 80.27}, {"lat": 13.0801, "lng": 80.2701}], "soil_type": "clay"}
    valid = {"x_m": 1, "y_m": 2, "soil_type": "sandy", "humidity_pct": 60, "depth_mm": 100, "hours_since_irrigation": 2}
    with TestClient(app) as client:
        client.post("/api/generate-mission", json=mission)
        assert client.post("/ai/predict-soil-moisture", json={**valid, "humidity_pct": 101}).status_code == 422
        response = client.post("/ai/predict-soil-moisture", json=valid)
    assert response.status_code == 200
    assert response.json()["source"] == "ML_MODEL"
    assert response.json()["soil_type"] == "clay"


def test_prediction_uses_threadpool_offload():
    """Inference is delegated through FastAPI's threadpool rather than blocking the event loop."""
    app.state.ai_status = "AI_AVAILABLE"
    app.state.ml_model = Mock()
    app.state.active_mission = {"field_id": "threadpool-field"}
    model_input = {"x_m": 1, "y_m": 2, "soil_type": "loam", "humidity_pct": 60, "depth_mm": 100, "hours_since_irrigation": 2}
    from ai.schemas import SoilPredictionInput
    with patch("ai.soil_predictor.run_in_threadpool", new_callable=AsyncMock, return_value=[42.0]) as threadpool:
        result = asyncio.run(predict_soil_moisture(app, SoilPredictionInput(**model_input)))
    assert result is not None and result.predicted_moisture_pct == 42.0
    assert threadpool.await_count == 1


def test_ai_unavailable_returns_503_without_affecting_health(monkeypatch):
    """A missing model disables only AI routes while the FastAPI service still starts normally."""
    monkeypatch.setattr("main.load_model_pipeline", lambda: None)
    valid = {"x_m": 1, "y_m": 2, "soil_type": "loam", "humidity_pct": 60, "depth_mm": 100, "hours_since_irrigation": 2}
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        response = client.post("/ai/predict-soil-moisture", json=valid)
    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "AI_UNAVAILABLE"
