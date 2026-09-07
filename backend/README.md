# AgriRover backend

This service provides deterministic convex-hull/Boustrophedon mission planning
and bridges the dashboard (`/ws/frontend`) with the rover (`/ws/esp32`).

Run locally:

```bash
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Useful endpoints are `GET /api/health` and `POST /api/generate-mission`.
Mission generation does not require an ESP32. The frontend WebSocket accepts
`START_MISSION` and `STOP_MISSION`; it returns the established
`MISSION_STARTED`/`MISSION_ERROR` messages. ESP32 JSON telemetry is relayed as
the established `TELEMETRY` envelope.

Run backend checks from this directory:

```bash
python -m pytest tests test_fastapi.py -v
```

The planner uses an equirectangular local projection intended only for the
small plots in this MVP. Shapely rotations explicitly set `use_radians=True`.
