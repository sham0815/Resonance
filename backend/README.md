# AgriRover Backend Service

The AgriRover backend is a high-performance FastAPI service providing:
1. **Deterministic Boustrophedon (Lawnmower) Path Planning**: Converts operator-drawn field boundaries on OpenStreetMap into continuous coverage paths and soil sampling points.
2. **Real-time WebSocket Telemetry & Mission Relay**: Bridges the React frontend (`/ws/frontend`) and ESP32 rover firmware (`/ws/esp32`).
3. **Isolated Soil-Moisture AI Estimation**: Evaluates a bundled `RandomForestRegressor` via FastAPI's threadpool to estimate soil moisture volumetric water content at unsampled grid points without blocking telemetry or navigation.

---

## Quickstart

### Prerequisites
- Python 3.11+
- Virtual environment with dependencies installed

### Running Locally
From the `backend/` directory:
```bash
# Activate existing virtual environment
source venv/bin/activate

# Install / update dependencies
pip install -r requirements.txt

# Start the uvicorn server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests
Run the complete unit and integration test suite:
```bash
python -m pytest tests test_fastapi.py -v
```
*Current status: 22/22 tests passing.*

---

## Core Endpoints & Protocols

### REST Endpoints
| Endpoint | Method | Description | Response / Status |
|---|---|---|---|
| `/api/health` | `GET` | Health check reporting service status, ESP32 connection, and AI availability | `{"status": "ok", "timestamp": ..., "esp32_connected": bool, "ai_status": "AI_AVAILABLE" \| "AI_UNAVAILABLE"}` |
| `/api/generate-mission` | `POST` | REST fallback for mission generation (usable without active WebSockets) | `{"status": "success", "mission_plan": {...}}` or `{"status": "error", "message": "..."}` |
| `/ai/predict-soil-moisture` | `POST` | Manual ML inference against active field context | `200 OK` with `PredictionResult` (`source: "ML_MODEL"`), or `503 Service Unavailable` if AI is unavailable |

### WebSocket Endpoints
- **`/ws/frontend`**:
  - Inbound: `{"type": "START_MISSION", "payload": {...}}`, `{"type": "STOP_MISSION"}`.
  - Outbound: `{"type": "MISSION_STARTED", "plan": {...}}`, `{"type": "MISSION_ERROR", "error": "..."}`, `{"type": "MISSION_STOPPED"}`, `{"type": "TELEMETRY", "payload": {...}}`, `{"type": "AI_SOIL_MOISTURE_PREDICTION", "payload": {...}}`.
- **`/ws/esp32`**:
  - Inbound: `{"type": "TELEMETRY", "payload": {...}}` or raw telemetry JSON.
  - Outbound: Sequential `{"cmd_id": int, "type": "WAYPOINT", "target_x_m": float, "target_y_m": float, "heading_deg": float, "action": "NAVIGATE" \| "SAMPLE_SOIL", ...}`.

---

## Architecture & Design Invariants

### 1. Deterministic Path Planner (`path_planner.py`)
- **Coordinate Transformer**: Equirectangular projection centered at the first boundary vertex ($R = 6,371,000\text{ m}$). Designed for small plots ($\le 500\text{ m}$).
- **Boundary Validation**:
  - Minimum 3 boundary vertices required.
  - Polygons must be simple (`MultiPoint.convex_hull`).
  - **Minimum Field Area**: Strictly `MIN_FIELD_AREA_M2 = 4.0` ($4.0\text{ m}^2$).
- **Boustrophedon Generation**:
  - Computes minimum bounding rectangle orientation.
  - **Radian Rotation Invariant**: Uses `shapely.affinity.rotate(..., use_radians=True)` to prevent radian/degree orientation mismatches.
  - Sweeps horizontal lines at `row_spacing_m` (default: $1.0\text{ m}$).
  - Inserts soil-sampling stop points along path segments at `sampling_density_m` (default: $3.0\text{ m}$).

### 2. AI Soil Moisture Prediction (`backend/ai/`)
- **Model**: `RandomForestRegressor` (`ai/model/soil_moisture_model.joblib`), trained with `seed=42`.
- **Feature Vector**: Strictly 6 input features:
  `[x_m, y_m, soil_type, humidity_pct, depth_mm, hours_since_irrigation]`
- **Target**: `soil_moisture_pct` (voluntarily clipped to $[0.0, 100.0]\%$).
- **Event-Loop Safety**: All ML inference runs off the async loop via FastAPI's `run_in_threadpool`.
- **Fault Tolerance**: If the model is absent or corrupt on startup, the application transitions to `AI_UNAVAILABLE` mode. All navigation, path planning, and telemetry bridging remain fully functional.

### 3. Data Integrity & Source Discrimination
Every telemetry-adjacent record is labeled with a single immutable source:
- `"SENSOR"`: Physical hardware probe reading (ground truth).
- `"ML_MODEL"`: Spatial interpolation prediction for unsampled grid points.
- `"SIMULATION"`: Mock data from test harness/simulator.

**Safety Invariants**:
- `ML_MODEL` predictions never overwrite physical `SENSOR` readings.
- `_ingest_telemetry` ignores `ML_MODEL` records, eliminating infinite recursive inference loops.
- Sensor readings are persisted to `backend/data/ai/soil_moisture_sensor_readings.jsonl`.
- Predictions are persisted to `backend/data/ai/soil_moisture_predictions.jsonl`.

### 4. Firmware-Not-Yet-Available Resilience
- All hardware-origin schema fields (`gps_lat`, `gps_lng`, `heading_deg`, `battery_pct`, probe readings) are typed `Optional[...] = None`.
- Never defaults to `0.0`, `0`, or `False` which could be confused with real zero readings.
- Mission planning and REST endpoints operate smoothly without an active ESP32 rover connection (`esp32_ws is None`).

---

## Scientific Honesty & Safety
- **Soil moisture measurements represent Volumetric Water Content only.** The backend never labels or implies moisture data as NPK, pH, organic matter, disease detection, or general crop health.
- **Fertilizer dosage is user-prescribed.** The backend never derives fertilizer doses from AI or sensor moisture values.
- **AI never influences navigation or safety systems.** Obstacle avoidance, E-stop, motor commands, and geofencing are 100% firmware/backend-deterministic.

