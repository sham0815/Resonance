# SW1_BACKEND_INSTRUCTIONS.md
### Backend & Path Planning — Owner: SW1

Branch: `sw1/backend`. You own everything under `backend/`. Do not touch `frontend/`. Your only contract with SW2 is the JSON schema in §6 below — if you need to change it, message SW2 before you do, not after.

Estimated time: ~6 hours to a working, tested backend.

---

## Step 1 — Dependencies (10 min)

```bash
cd backend
source venv/bin/activate
```

Create `backend/requirements.txt`:

```text
fastapi==0.109.0
uvicorn[standard]==0.27.0
shapely==2.0.3
numpy==1.26.3
pandas==2.2.0
pydantic==2.5.3
python-multipart==0.0.6
websockets==12.0
pytest==8.0.0
```

```bash
pip install -r requirements.txt
```

**Verify:** `python -c "import shapely, fastapi, numpy; print('ok')"` prints `ok`.

---

## Step 2 — Path Planner (`backend/path_planner.py`) (2 hrs)

This is the deterministic core: GPS → local Cartesian → convex hull → oriented bounding box → Boustrophedon grid → back to GPS.

Create `backend/path_planner.py`:

```python
"""
Autonomous Precision Agriculture Rover - Path Planner
Converts a Google-Maps-clicked field boundary into a Boustrophedon coverage path.

Public entrypoint:
    planner = ConvexHullPlanner(row_spacing_m=1.0)
    mission_plan = planner.generate_grid(user_points)
"""

import math
from typing import List, Dict, Tuple
from shapely.geometry import Polygon, MultiPoint, LineString
from shapely.affinity import rotate
import numpy as np


class CoordinateTransformer:
    """Converts GPS coordinates to a local Cartesian plane and back.

    Uses an equirectangular (small-area) approximation anchored at a home
    point. Valid for areas up to a few hundred meters across — well within
    a 10x10m hackathon plot. Do NOT reuse this for large-area farms without
    switching to a proper projected CRS (e.g. UTM via pyproj).
    """

    def __init__(self, home_lat: float, home_lng: float):
        self.home_lat = home_lat
        self.home_lng = home_lng
        self.R = 6371000  # mean Earth radius, meters

    def gps_to_local(self, lat: float, lng: float) -> Tuple[float, float]:
        lat_rad = math.radians(lat)
        lng_rad = math.radians(lng)
        home_lat_rad = math.radians(self.home_lat)
        home_lng_rad = math.radians(self.home_lng)

        dlat = lat_rad - home_lat_rad
        dlng = lng_rad - home_lng_rad

        x = dlng * self.R * math.cos(home_lat_rad)  # east-west
        y = dlat * self.R                             # north-south
        return (x, y)

    def local_to_gps(self, x: float, y: float) -> Tuple[float, float]:
        dlat = y / self.R
        dlng = x / (self.R * math.cos(math.radians(self.home_lat)))
        lat = math.degrees(math.radians(self.home_lat) + dlat)
        lng = math.degrees(math.radians(self.home_lng) + dlng)
        return (lat, lng)


class ConvexHullPlanner:
    """Generates a Boustrophedon (lawnmower) coverage path for a convex field.

    Pipeline:
      1. GPS points -> local Cartesian (anchored at first point)
      2. Convex hull (tolerates imprecise clicking)
      3. Minimum-area oriented bounding box -> optimal grid angle
      4. Rotate hull to axis-align, sweep horizontal lines, clip to hull
      5. Rotate waypoints back, insert soil-sampling sub-points
      6. Map back to GPS for the frontend map overlay
    """

    def __init__(self, row_spacing_m: float = 1.0, sampling_density_m: float = 3.0):
        self.row_spacing = row_spacing_m
        self.sampling_density = sampling_density_m

    def generate_grid(self, user_points: List[Dict[str, float]]) -> Dict:
        if len(user_points) < 3:
            raise ValueError("Minimum 3 boundary points required")

        transformer = CoordinateTransformer(user_points[0]["lat"], user_points[0]["lng"])
        local_points = [transformer.gps_to_local(p["lat"], p["lng"]) for p in user_points]

        hull = MultiPoint(local_points).convex_hull
        if not isinstance(hull, Polygon):
            raise ValueError("Points do not form a valid polygon (collinear or duplicate points)")
        if hull.area < 4.0:
            raise ValueError(f"Field area {hull.area:.2f} m² is below the 4 m² minimum")

        min_rect = self._minimum_bounding_rectangle(hull)
        grid_angle = min_rect["orientation"]
/* Lines 128-150 omitted */
        }

    def _minimum_bounding_rectangle(self, polygon: Polygon) -> Dict:
        coords = list(polygon.exterior.coords)[:-1]
        /* Lines 154-170 omitted */
        return best

    def _generate_axis_aligned_grid(self, polygon: Polygon) -> List[Tuple[float, float]]:
        minx, miny, maxx, maxy = polygon.bounds
        /* Lines 174-192 omitted */
        return waypoints

    def _insert_sampling_points(self, path: List[Tuple[float, float]], density_m: float) -> List[Tuple[float, float]]:
        if len(path) < 2:
            /* Lines 196-210 omitted */
        return sampling_points

    def _path_length(self, path: List[Tuple[float, float]]) -> float:
        if len(path) < 2:
            /* Lines 214-218 omitted */
        )

    def _rotate_point(self, point: Tuple[float, float], angle: float, origin: Tuple[float, float]) -> Tuple[float, float]:
        x, y = point
        /* Lines 222-226 omitted */
        return (x_new + ox, y_new + oy)
```

**Note on a bug in earlier drafts:** the previous version rotated the hull with `rotate(polygon, -angle, ...)` where `angle` was in radians but Shapely's `rotate()` defaults to **degrees**. This version explicitly passes `use_radians=True` everywhere a radian angle is used — check this if you ever see a grid rotated wildly off-orientation.

**Verify:**
```bash
python -c "
from path_planner import ConvexHullPlanner
pts = [
    {'lat': 13.08271, 'lng': 80.27072},
    {'lat': 13.08301, 'lng': 80.27151},
    {'lat': 13.08221, 'lng': 80.27202},
    {'lat': 13.08181, 'lng': 80.27121},
]
plan = ConvexHullPlanner(row_spacing_m=1.0).generate_grid(pts)
print('area:', plan['hull_area_m2'])
print('waypoints:', len(plan['waypoints_local']))
"
```
Expect a positive area and at least a few waypoints. If it raises `ValueError` about area, your test points are too close together — space them out.

---

## Step 3 — Unit Tests (30 min)

Create `backend/tests/test_path_planner.py`:

```python
import pytest
from path_planner import ConvexHullPlanner, CoordinateTransformer


def test_transformer_round_trip():
    t = CoordinateTransformer(13.0827, 80.2707)
    x, y = t.gps_to_local(13.0830, 80.2710)
    lat, lng = t.local_to_gps(x, y)
    assert abs(lat - 13.0830) < 1e-6
    assert abs(lng - 80.2710) < 1e-6


def test_rejects_too_few_points():
    with pytest.raises(ValueError):
        ConvexHullPlanner().generate_grid([{"lat": 0, "lng": 0}, {"lat": 0, "lng": 0.0001}])


def test_rejects_tiny_area():
    pts = [
        {"lat": 13.0000, "lng": 80.0000},
        /* Lines 275-276 omitted */
        {"lat": 13.00001, "lng": 80.00001},
    ]
    with pytest.raises(ValueError):
        ConvexHullPlanner().generate_grid(pts)


def test_generates_waypoints_for_square_field():
    # ~10x10m square
    pts = [
        {"lat": 13.08000, "lng": 80.27000},
        /* Lines 286-288 omitted */
        {"lat": 13.08009, "lng": 80.27000},
    ]
    plan = ConvexHullPlanner(row_spacing_m=1.0).generate_grid(pts)
    assert plan["hull_area_m2"] > 4.0
    assert len(plan["waypoints_local"]) > 5
    assert plan["total_distance_m"] > 0
    assert len(plan["waypoints_gps"]) == len(plan["waypoints_local"]) 
```

```bash
cd backend
pytest tests/ -v
```
All 4 tests should pass before you move on.

---

## Step 4 — FastAPI Server (`backend/main.py`) (2 hrs)

```python
"""
Autonomous Precision Agriculture Rover - FastAPI Backend
Bridges the React frontend, the ESP32 firmware, and the path planner.

Run:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import math
import time
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from path_planner import ConvexHullPlanner

app = FastAPI(title="AgriRover Mission Planner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon-only; restrict to frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

planner = ConvexHullPlanner(row_spacing_m=1.0, sampling_density_m=3.0)

esp32_ws: Optional[WebSocket] = None
frontend_ws: Optional[WebSocket] = None


class FieldBoundary(BaseModel):
    field_id: str
    boundary_points: List[Dict[str, float]]
    row_spacing_m: float = 1.0
    sampling_density_m: float = 3.0
    active_payload: str = "IRRIGATION"
    prescription: Dict = {}


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/api/generate-mission")
async def generate_mission(boundary: FieldBoundary):
    """REST fallback for mission generation — useful for SW2 to test the map UI
    without a live WebSocket/ESP32 connection."""
    try:
        plan = ConvexHullPlanner(
            /* Lines 364-367 omitted */
        return {"status": "success", "mission_plan": plan}
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@app.websocket("/ws/esp32")
async def esp32_endpoint(websocket: WebSocket):
    global esp32_ws
    await websocket.accept()
    esp32_ws = websocket
    print("ESP32 connected")
    try:
        while True:
    except WebSocketDisconnect:
        esp32_ws = None
        print("ESP32 disconnected")


@app.websocket("/ws/frontend")
async def frontend_endpoint(websocket: WebSocket):
    global frontend_ws
    await websocket.accept()
    frontend_ws = websocket
    print("Frontend connected")
    try:
        while True:
    except WebSocketDisconnect:
        frontend_ws = None
        print("Frontend disconnected")


async def _handle_start_mission(websocket: WebSocket, payload: dict):
    try:
        boundary = FieldBoundary(**payload)
        /* Lines 413-441 omitted */
        await websocket.send_text(json.dumps({"type": "MISSION_STARTED", "plan": plan}))
    except ValueError as e:
        await websocket.send_text(json.dumps({"type": "MISSION_ERROR", "error": str(e)}))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Fix applied vs. earlier draft:** the original inlined waypoint-sending logic directly in the WebSocket loop and called `math.atan2` without importing `math` at module scope in some versions — this version imports `math` at the top and factors mission handling into `_handle_start_mission` so it's independently testable.

**Verify:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
In another terminal: `curl http://localhost:8000/api/health` → `{"status":"ok",...}`.

Then test the REST fallback:
```bash
curl -X POST http://localhost:8000/api/generate-mission \
  -H "Content-Type: application/json" \
  -d '{
    "field_id": "test",
    /* Lines 465-470 omitted */
    ]
  }'
```
Expect `"status": "success"` with a populated `mission_plan`.

---

## Step 5 — `.env.example` (5 min)

```text
# backend/.env.example
HOST=0.0.0.0
PORT=8000
ROW_SPACING_M=1.0
SAMPLING_DENSITY_M=3.0
```
(These aren't wired into `main.py` by default in the MVP — hardcoded defaults are fine for a hackathon. Wire them in with `python-dotenv` only if time allows.)

---

## Step 6 — Data Contract With SW2 (read this, don't just skim)

This is the exact shape SW2's frontend sends and expects. Do not change field names without telling SW2.

**Frontend → Backend (`START_MISSION` over `/ws/frontend`, or POST `/api/generate-mission`):**
```json
{
  "type": "START_MISSION",
  "payload": {
    "field_id": "field_alpha",
    /* Lines 500-504 omitted */
    "prescription": {}
  }
}
```

**Backend → Frontend (mission accepted):**
```json
{
  "type": "MISSION_STARTED",
  "plan": {
    "hull_area_m2": 100.0,
    /* Lines 515-520 omitted */
    "estimated_time_min": 5.0
  }
}
```

**Backend → Frontend (mission rejected):**
```json
{"type": "MISSION_ERROR", "error": "Minimum 3 boundary points required"}
```

**Backend → Frontend (telemetry relay, sourced from ESP32):**
```json
{"type": "TELEMETRY", "payload": { "...": "see README §Data Schemas" }}
```

If you change any key name here, ping SW2 in the same message you push the commit — this is the #1 source of hour-18 integration failures.

---

## Step 7 — Self-Test Checklist Before Integration Hour

- [ ] `pytest tests/ -v` passes
- [ ] `uvicorn main:app` starts with no errors, `/api/health` responds
- [ ] `/api/generate-mission` returns a valid plan for a test square
- [ ] `/ws/frontend` accepts a connection (test with a WebSocket client like `websocat` or Postman) and responds to `START_MISSION` with `MISSION_STARTED`
- [ ] Behavior when `esp32_ws` is `None` (ESP32 not yet connected) doesn't crash — mission plan should still be generated and returned to the frontend even with no rover attached
- [ ] Committed and pushed to `sw1/backend`, PR opened against `main`
