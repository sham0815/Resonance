# INTEGRATION_TESTING.md
### End-to-End Integration & Testing Protocol

This runs at the **hour-18 critical milestone** from the master timeline, and again at hour 24 and hour 36. All four team members should be present for at least the first pass.

---

## 1. Pre-Integration Checklist

Before connecting anything physically, confirm each track passed its own self-test:

- [ ] SW1: `SW1_BACKEND_INSTRUCTIONS.md` §7 checklist complete
- [ ] SW2: `SW2_FRONTEND_INSTRUCTIONS.md` §10 checklist complete
- [ ] HW2: Rover drives straight on IMU-fused PID heading control (no ESP32↔laptop link needed for this)
- [ ] HW1: Soil probe mechanically deploys/retracts on a bench test (no live sensor read needed yet)
- [ ] Both feature branches merged into `main`, `main` builds/runs cleanly on a fresh clone

If any box is unchecked, fix it before proceeding — integration debugging is much harder when you can't tell if a failure is in your own module or at the seam.

---

## 2. Network Setup (10 min)

1. Power on the portable router. Confirm laptop and ESP32 are both configured to join the **same** SSID.
2. Find the laptop's LAN IP:
   ```bash
   # macOS/Linux
   ifconfig | grep "inet "
   # Windows
   ipconfig
   ```
3. Update `firmware/esp32_main.ino`:
   ```cpp
   const char* WIFI_SSID = "<actual hackathon SSID>";
   const char* WIFI_PASSWORD = "<actual password>";
   const char* WEBSOCKET_SERVER = "<laptop LAN IP found above>";
   ```
4. Re-flash the ESP32 with the updated IP. **This step is the #1 cause of "nothing happens" at integration time** — a stale hardcoded IP from an earlier test network. Double check it every time you switch networks (e.g. moving from a home Wi-Fi test to the venue's router).

---

## 3. Layered Integration — Test in This Order, Not All at Once

Trying to validate the whole pipeline in one shot makes it nearly impossible to localize a failure. Go layer by layer.

### Layer 1 — Backend alone
```bash
cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
curl http://localhost:8000/api/health
```
Expect: `{"status": "ok", ...}`. If this fails, stop — nothing downstream can work.

### Layer 2 — Frontend ↔ Backend (no ESP32)
1. Start backend (Layer 1).
2. `cd frontend && npm run dev`, open the app.
3. Header should show **● Backend connected** within ~1 second.
4. Click 3–4 map points, click "Finish Field & Start Mission."
5. Expect: Mission Status panel populates with real area/distance/waypoint numbers, red waypoint dots appear on the map.

If this fails: check the browser console for WebSocket errors, check `VITE_BACKEND_WS_URL` matches the backend's actual host:port, check CORS isn't blocking (should be `allow_origins=["*"]` per SW1's `main.py`).

### Layer 3 — ESP32 ↔ Backend (no frontend needed, or frontend running for visibility)
1. Power on the rover with firmware flashed per §2.
2. Watch the ESP32 serial monitor (115200 baud): expect `WiFi connected`, then `WebSocket connected`.
3. Watch the backend terminal: expect `ESP32 connected` printed.
4. If the frontend is also running, telemetry should start appearing in the Live Telemetry panel within ~1 second of ESP32 connecting (the 1-second `TELEMETRY_INTERVAL` in firmware).

If this fails: check the WEBSOCKET_SERVER IP again, check the ESP32 and laptop are actually on the same subnet (not laptop on 5GHz-guest and ESP32 on 2.4GHz-main if the router splits them), check the backend logs for connection attempts.

### Layer 4 — Full Loop: Map Click → Path Plan → ESP32 Waypoints → Physical Motion
1. All three layers above working simultaneously.
2. Draw a small (~2x2m) test boundary on the map that corresponds to a real taped-out square on the floor (use the venue's actual GPS coordinates — get them from your phone's Maps app standing at the test area).
3. Click "Finish Field & Start Mission."
4. Expect: backend logs show waypoint commands being sent (`cmd_id 0, 1, 2...`), ESP32 serial monitor shows `WAYPOINT n: (x, y) heading h` for each, rover physically moves in a lawnmower pattern within the taped square.
5. Watch the dashboard's blue rover marker track (approximately) the physical motion.

This is the milestone deliverable for hour 18: **"Rover completes autonomous square mission."**

---

## 4. Hardware-Software Integration Checklist

- [ ] ESP32 firmware IP/SSID matches the actual venue network
- [ ] `WEBSOCKET_TIMEOUT` (5000ms) fires correctly: unplug the router mid-mission, confirm motors stop within 5 seconds and firmware state goes to `COMM_LOST`
- [ ] Reconnecting Wi-Fi within a mission causes the ESP32 to resume accepting commands (state returns from `COMM_LOST` to `IDLE`)
- [ ] Battery voltage divider is calibrated — compare `readBatteryVoltage()` serial output against a multimeter reading on the actual pack
- [ ] Soil sensor analog readings are sane (0–100% range, not pinned at 0 or 100) — calibrate `readSoilMoisture()`'s scaling against a dry cup of soil and a wet cup of soil
- [ ] E-stop button physically cuts motor power (test by pressing it mid-motion, confirm motors stop even if firmware logic doesn't)
- [ ] Tilt detection (>45°) actually halts motors — test by lifting one side of the chassis during a drive test

---

## 5. Common Failure Modes & Debugging Steps

| Symptom | Likely Cause | Fix |
|---|---|---|
| Frontend shows "Backend offline" | Backend not running, or wrong `VITE_BACKEND_WS_URL` | Confirm `uvicorn` is running; check `.env.local` matches actual backend port |
| Mission plan never returns, no error shown | WebSocket connected but `START_MISSION` payload key mismatch | Compare frontend payload against `SW1_BACKEND_INSTRUCTIONS.md` §6 exactly, field-by-field |
| `MISSION_ERROR: Minimum 4 m² required` on a real field | Points clicked too close together, or accidentally double-clicked the same spot | Re-click with points spread around the actual perimeter |
| ESP32 never shows `WiFi connected` in serial monitor | Wrong SSID/password, or 5GHz-only network (ESP32 is 2.4GHz only) | Verify router broadcasts 2.4GHz; re-check credentials |
| ESP32 connects to WiFi but never `WebSocket connected` | Wrong `WEBSOCKET_SERVER` IP, laptop firewall blocking port 8000 | Re-verify laptop IP; temporarily disable firewall or add an inbound rule for port 8000 |
| Rover drives in the wrong direction / spins in place | IMU heading sign convention mismatch with motor direction wiring | Check `moveMotors()` sign convention against actual left/right motor wiring; swap `IN1`/`IN2` if reversed |
| Rover overshoots waypoints / oscillates | PID gains too aggressive for the actual chassis mass/speed | Retune `Kp/Ki/Kd` in `esp32_main.ino`, starting by lowering `Kp` |
| Dashboard rover marker doesn't move | ESP32 firmware `gps_lat`/`gps_lng` telemetry fields hardcoded to `0.0` (see firmware TODO) | Wire actual GPS module reads into `sendTelemetry()`, or fall back to plotting `current_x_m`/`current_y_m` converted through the same `CoordinateTransformer` origin on the frontend for the demo |
| Mission "starts" but ESP32 never receives waypoints | `esp32_ws` was `None` in the backend when `START_MISSION` fired (ESP32 connected after mission was requested) | Ensure ESP32 connects *before* clicking "Finish Field" during demo; consider adding a "rover ready" indicator to the dashboard |

---

## 6. Final Verification Before Demo (Hour 42+ Feature Freeze)

Run this exact sequence three times in a row, successfully, before declaring the system demo-ready:

1. Power everything on from cold (router, laptop, rover) in the actual demo location.
2. Confirm dashboard shows "Backend connected."
3. Confirm ESP32 serial log (or a dashboard "rover connected" indicator, if you built one) shows the ESP32 is linked.
4. Draw the demo field boundary on the map.
5. Click "Finish Field & Start Mission."
6. Rover completes the full Boustrophedon pattern without a STUCK, COMM_LOST, or LOW_BATTERY interruption.
7. At least one soil sampling point executes (probe lowers, waits, reads, raises) and the telemetry panel shows a plausible moisture percentage.
8. Dashboard "Resources Used" panel reflects any irrigation/seeding/fertilizer actions taken.
9. Rover reaches `MISSION_COMPLETE` and stops cleanly.

If any of the three dry runs fails, do not change code between attempts without re-running all three from a cold start — flaky failures under time pressure are almost always network or power related, not logic bugs, and a code change without re-testing risks masking the real cause.

---

## 7. Judge-Facing Safety Demo (Optional but High-Value)

If time allows after §6 passes three times, stage a short deliberate-failure demo for judges:
- Mid-mission, pull the router's power → show motors halting within 5 seconds (`COMM_LOST`).
- Press the physical E-stop → show immediate motor cutoff regardless of firmware state.

This directly answers two of the "Expected Judge Questions" from the master prompt (§14: comm loss, E-stop) with a live demonstration instead of a verbal answer, which is significantly more convincing under judging pressure.
