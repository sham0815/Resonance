import json

from fastapi.testclient import TestClient

from main import app


VALID_REQUEST = {
    "field_id": "test",
    "boundary_points": [
        {"lat": 13.08000, "lng": 80.27000},
        {"lat": 13.08010, "lng": 80.27000},
        {"lat": 13.08010, "lng": 80.27010},
        {"lat": 13.08000, "lng": 80.27010},
    ],
    "row_spacing_m": 1.0,
    "sampling_density_m": 3.0,
    "active_payload": "IRRIGATION",
    "prescription": {},
}


def test_health_reports_no_hardware_as_healthy():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["esp32_connected"] is False


def test_rest_generates_mission_without_esp32():
    with TestClient(app) as client:
        response = client.post("/api/generate-mission", json=VALID_REQUEST)
    result = response.json()
    assert response.status_code == 200
    assert result["status"] == "success"
    assert result["mission_plan"]["field_id"] == "test"
    assert result["mission_plan"]["total_distance_m"] > 0


def test_rest_returns_controlled_error_for_invalid_geometry():
    request = {**VALID_REQUEST, "boundary_points": VALID_REQUEST["boundary_points"][:2]}
    with TestClient(app) as client:
        response = client.post("/api/generate-mission", json=request)
    assert response.status_code == 200
    assert response.json() == {"status": "error", "message": "Minimum 3 boundary points required"}


def test_frontend_websocket_start_invalid_and_stop_without_esp32():
    with TestClient(app) as client, client.websocket_connect("/ws/frontend") as websocket:
        websocket.send_text(json.dumps({"type": "START_MISSION", "payload": VALID_REQUEST}))
        started = websocket.receive_json()
        assert started["type"] == "MISSION_STARTED"
        assert started["plan"]["field_id"] == "test"
        websocket.send_text(json.dumps({"type": "START_MISSION", "payload": {"field_id": "bad"}}))
        assert websocket.receive_json()["type"] == "MISSION_ERROR"
        websocket.send_text(json.dumps({"type": "STOP_MISSION"}))
        assert websocket.receive_json()["type"] == "MISSION_STOPPED"


def test_esp32_telemetry_is_relayed_to_frontend():
    telemetry = {"rover_status": "IDLE", "battery_pct": 84}
    with TestClient(app) as client, client.websocket_connect("/ws/frontend") as frontend, client.websocket_connect("/ws/esp32") as esp32:
        esp32.send_text(json.dumps(telemetry))
        assert frontend.receive_json() == {"type": "TELEMETRY", "payload": telemetry}


def test_mission_is_forwarded_to_connected_esp32():
    with TestClient(app) as client, client.websocket_connect("/ws/esp32") as esp32, client.websocket_connect("/ws/frontend") as frontend:
        frontend.send_text(json.dumps({"type": "START_MISSION", "payload": VALID_REQUEST}))
        assert frontend.receive_json()["type"] == "MISSION_STARTED"
        first_command = esp32.receive_json()
        assert first_command["type"] == "WAYPOINT"
        assert first_command["action"] == "NAVIGATE"
