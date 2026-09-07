# AgriRover — Autonomous Precision Agriculture Rover

A 48-hour hackathon MVP: draw a field boundary on OpenStreetMap, and an autonomous rover navigates it in a Boustrophedon (lawnmower) coverage pattern, sampling soil moisture and executing a user-prescribed treatment (seeding, irrigation, or fertilizer) along the way.

**Design philosophy:** deterministic math for deterministic problems (path planning), physical sensors for direct measurements (soil moisture, heading, distance), and AI only where genuine spatial uncertainty exists (soil moisture interpolation between sample points). GPS is used for a global origin lock and geofencing only — not for live navigation, since consumer GPS's ~2.5m CEP is unusable for centimeter-scale row-following on a 10×10m plot.

---

## Repository Structure

```
agri-rover/
├── backend/       FastAPI server + Boustrophedon path planner (SW1)
├── frontend/      React + TypeScript + OpenStreetMap dashboard (SW2)
├── firmware/      ESP32 C++ firmware (HW2, integrated by SW1)
├── docs/          This documentation set
└── README.md
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- OpenStreetMap tiles through Leaflet (no map API key required)
- ESP32-WROOM-32E with the components listed in the BOM below, flashed via Arduino IDE or PlatformIO

### Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local   # then set the backend WebSocket URL if needed
npm run dev
```
Open `http://localhost:3000`.

### Firmware
1. Open `firmware/esp32_main.ino` in Arduino IDE.
2. Install libraries: `arduinoWebSockets`, `ArduinoJson`, `MPU6050_light`, `PID_v1`.
3. Set `WIFI_SSID`, `WIFI_PASSWORD`, and `WEBSOCKET_SERVER` (your laptop's LAN IP) at the top of the file.
4. Flash to the ESP32, open the serial monitor at 115200 baud.

Full setup detail: see `docs/SETUP_BASE.md`, `docs/SW1_BACKEND_INSTRUCTIONS.md`, `docs/SW2_FRONTEND_INSTRUCTIONS.md`.

---

## System Architecture

```
[User clicks boundary on Google Maps]
            │
            ▼
[React frontend] ──WebSocket──▶ [FastAPI backend]
            ▲                         │
            │                    convex hull → OBB →
       telemetry                 Boustrophedon path
            │                         │
            └────────WebSocket────────┤
                                       ▼
                              [ESP32 firmware]
                          IMU+Mag heading PID,
                       encoder distance tracking,
                        GPS geofence, safety FSM
                                       │
                                       ▼
                          [Motors, servos, sensors]
```

### Waypoint Taxonomy
```
[FIELD BOUNDARY POINTS]  --> User-clicked points on Google Maps
          │
          ▼ (convex hull)
[CONVEX HULL POLYGON]    --> Cleaned boundary for path planning
          │
          ▼ (Boustrophedon)
[NAVIGATION WAYPOINTS]   --> Trajectory path nodes for motion control
          │
          ├─────────────────► [SOIL SAMPLING POINTS] --> Physical stop & sensor insertion
          │
          └─────────────────► [TREATMENT POINTS]     --> Action execution (Seed/Water/Fertilizer)
```

---

## Navigation Approach

Standard GNSS (e.g. NEO-6M) has ~2.5m Circular Error Probable — unusable for steering on a 10×10m plot with 1m row spacing. Navigation instead uses local sensor fusion:

1. **GPS Start Lock** — establishes the global origin and verifies the rover starts inside the field boundary.
2. **IMU + Magnetometer heading** — MPU6050 gyro + HMC5883L/QMC5883L magnetometer, fused via complementary filter (`yaw = 0.98*(yaw_prev + gyro*dt) + 0.02*magnetometer_heading`), locked via a local PID loop.
3. **Encoder distance tracking** — differential-drive kinematics from wheel encoders.
4. **GPS geofence check** — runs in the background as an out-of-bounds failsafe only, never as a steering input.

---

## Data Schemas

**Mission Generation (Frontend → Backend):**
```json
{
  "field_id": "field_alpha",
  "boundary_points": [{"lat": 13.08271, "lng": 80.27072}],
  "row_spacing_m": 1.0,
  "sampling_density_m": 3.0,
  "active_payload": "IRRIGATION",
  "prescription": {"dose_grams": 0, "spacing_m": 0}
}
```

**Executable Waypoint (Backend → ESP32):**
```json
{
  "cmd_id": 104,
  "type": "WAYPOINT",
  "target_x_m": 4.5,
  "target_y_m": 12.0,
  "heading_deg": 90.0,
  "action": "SAMPLE_SOIL",
  "payload_param": 0,
  "timeout_ms": 30000,
  "checksum": "a3f2"
}
```

**Live Telemetry (ESP32 → Backend → Frontend):**
```json
{
  "timestamp": 1772922123,
  "rover_status": "NAVIGATING",
  "current_x_m": 4.48,
  "current_y_m": 11.95,
  "heading_deg": 89.2,
  "gps_lat": 13.08275,
  "gps_lng": 80.27081,
  "soil_moisture_pct": 34.2,
  "battery_pct": 84,
  "active_payload": "IRRIGATION",
  "resources_used": {"fertilizer_g": 0, "water_ml": 0, "seeds": 0}
}
```

Full contract, including the `MISSION_STARTED`/`MISSION_ERROR` responses: `docs/SW1_BACKEND_INSTRUCTIONS.md` §6.

---

## Safety Systems

| System | Trigger | Response |
|---|---|---|
| Communication watchdog | No WebSocket packet for 5s | All motors/actuators halt, state → `COMMUNICATION_LOST` |
| Hardware E-stop | Physical mushroom button (NC contacts) | Cuts main power to motor drivers and actuator buck converter directly, independent of firmware |
| Low-voltage cutoff | Battery < 10.5V (alert) / < 9.6V (hard cutoff) | Alert at 10.5V, motor shutdown at 9.6V |
| Stuck detection | Encoder counts < threshold for 5s while PWM > 50% | State → `STUCK`, reverse 0.5m, retry |
| Tilt detection | MPU6050 reads > 45° tilt | Immediate motor shutdown |

---

## Modular Payload System

One universal payload slot with a quick-latch mount and a 4-pin JST-XH header (Power, Ground, Signal 1, Signal 2). **One treatment at a time** — the operator physically mounts the correct module before a mission phase:

- **Module A — Seeding:** hopper + servo-driven dispensing gate
- **Module B — Irrigation:** 12V DC pump + MOSFET switch + spray nozzle
- **Module C — Fertilizer:** hopper + calibrated servo slide gate (dose set by user prescription, never derived from soil moisture)

The permanently-mounted soil probe (MG996 servo arm + capacitive sensor) follows: lower → wait 3s → read → raise, only at dedicated sampling waypoints.

---

## Scientific Honesty Notes

- Soil moisture sensors measure **volumetric water content only** — not NPK, pH, or organic matter. Any framing implying otherwise is inaccurate.
- Fertilizer dosing is **always** a user-entered agronomic prescription, never derived from moisture data.
- IMU drift is *mitigated* by the magnetometer fusion, not eliminated.
- Spatial interpolation (IDW) is deterministic math, not a trained ML model — no accuracy claims beyond "matches the interpolation method's known behavior."
- Wheel slip is not actively compensated in this MVP.
- Concave field boundaries are not supported in the MVP (future work: polygon decomposition).

---

## Bill of Materials

| Component | Purpose | Approx. Cost |
|---|---|---|
| ESP32-WROOM-32E | Main controller | $6 |
| MPU6050 | IMU (gyro + accel) | $3 |
| HMC5883L / QMC5883L | Magnetometer | $3 |
| NEO-6M GPS | Geofence only | $12 |
| TB6612FNG ×2 | Motor drivers | $4 |
| MG996 ×2 | Probe + payload servos | $10 |
| Capacitive soil sensor v1.2 | Moisture | $8 |
| 3S 5000mAh 30C LiPo | Main battery | $25 |
| LM2596 ×2 | Buck converters | $4 |
| 12V diaphragm pump | Irrigation | $15 |
| IRF520 MOSFET | Pump/valve switch | $2 |
| Misc. (diodes, caps, E-stop, wheels) | Protection & mechanical | ~$17 |
| **Total** | | **~$109** |

---

## Documentation Index

- [`docs/SETUP_BASE.md`](docs/SETUP_BASE.md) — repository init, branch strategy, environment setup
- [`docs/SW1_BACKEND_INSTRUCTIONS.md`](docs/SW1_BACKEND_INSTRUCTIONS.md) — path planner, FastAPI server, data contract
- [`docs/SW2_FRONTEND_INSTRUCTIONS.md`](docs/SW2_FRONTEND_INSTRUCTIONS.md) — React dashboard, WebSocket hook, UI components
- [`docs/INTEGRATION_TESTING.md`](docs/INTEGRATION_TESTING.md) — layered integration protocol, failure-mode table, demo verification

---

## Anticipated Judge Questions

See `docs/INTEGRATION_TESTING.md` §7 for a live-demo approach to the two most common ones (comm loss, E-stop). Written answers to the full set (AI usage boundaries, GPS accuracy, soil sensor scope, RTK tradeoffs, ROS tradeoffs, scalability) are preserved from the original design spec and should be rehearsed verbally rather than read from a slide.
