# SW2_FRONTEND_INSTRUCTIONS.md
### Frontend & Dashboard — Owner: SW2

Branch: `sw2/frontend`. You own everything under `frontend/`. Do not touch `backend/`. Your only contract with SW1 is the JSON schema in `SW1_BACKEND_INSTRUCTIONS.md` §6 — treat it as fixed unless you've explicitly agreed a change with SW1.

Estimated time: ~6 hours to a working, demo-ready dashboard.

---

## Step 1 — Scaffold & Dependencies (15 min)

If not already scaffolded in `SETUP_BASE.md`:
```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
```

Install the rest:
```bash
npm install @react-google-maps/api
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

`frontend/tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

`frontend/src/index.css` (create if missing):
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```
Import it once in `frontend/src/main.tsx`: `import './index.css'`.

**Verify:** `npm run dev` → open `http://localhost:3000` (see vite.config.ts below) → Vite/React starter page renders.

---

## Step 2 — Vite Config (5 min)

`frontend/vite.config.ts`:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

---

## Step 3 — Environment Variables (5 min)

`frontend/.env.example`:
```text
VITE_GOOGLE_MAPS_API_KEY=YOUR_GOOGLE_MAPS_API_KEY_HERE
VITE_BACKEND_WS_URL=ws://localhost:8000/ws/frontend
```

Copy to `frontend/.env.local` (gitignored) and fill in a real key.

**⚠️ Security warning — read before committing anything:**
- Never commit `.env.local` or any file containing a real API key. Confirm `.gitignore` covers `.env.local` (see `SETUP_BASE.md`).
- In the Google Cloud Console, restrict the Maps JavaScript API key to **HTTP referrers** (`localhost:3000/*` and your demo laptop's LAN IP) before the hackathon starts, not after — an unrestricted key committed to a public repo will get scraped and billed within minutes.
- If a key does leak into a commit, rotate it immediately in the Cloud Console; `git revert` does not remove it from GitHub's history.

---

## Step 4 — Shared Types (`frontend/src/types.ts`) (10 min)

Centralize the data contract from `SW1_BACKEND_INSTRUCTIONS.md` §6 so both of you can grep one file when the schema is in question:

```ts
export interface LatLng {
  lat: number;
  lng: number;
}

export interface MissionPlan {
  field_id: string;
  hull_area_m2: number;
  grid_orientation_deg: number;
  waypoints_local: [number, number][];
  waypoints_gps: LatLng[];
  sampling_points: [number, number][];
  total_distance_m: number;
  estimated_time_min: number;
}

export interface ResourcesUsed {
  fertilizer_g: number;
  water_ml: number;
  seeds: number;
}

export interface TelemetryData {
  timestamp: number;
  rover_status:
    | 'IDLE'
    | 'NAVIGATING'
    | 'ARRIVED_AT_NODE'
    | 'PERFORMING_ACTION'
    | 'COMM_LOST'
    | 'LOW_BATTERY'
    | 'STUCK'
    | 'MISSION_COMPLETE';
  current_x_m: number;
  current_y_m: number;
  heading_deg: number;
  gps_lat: number;
  gps_lng: number;
  soil_moisture_pct: number;
  battery_pct: number;
  active_payload: string;
  resources_used: ResourcesUsed;
}

export type BackendMessage =
  | { type: 'MISSION_STARTED'; plan: MissionPlan }
  | { type: 'MISSION_ERROR'; error: string }
  | { type: 'TELEMETRY'; payload: TelemetryData };
```

---

## Step 5 — WebSocket Hook (`frontend/src/hooks/useMissionSocket.ts`) (30 min)

Isolating the WebSocket into a hook keeps `App.tsx` readable and makes reconnection logic testable on its own.

```ts
import { useEffect, useRef, useState, useCallback } from 'react';
import type { BackendMessage, MissionPlan, TelemetryData, LatLng } from '../types';

const WS_URL = import.meta.env.VITE_BACKEND_WS_URL || 'ws://localhost:8000/ws/frontend';

export function useMissionSocket() {
  const [connected, setConnected] = useState(false);
  const [missionPlan, setMissionPlan] = useState<MissionPlan | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setError('WebSocket connection error — is the backend running?');

    ws.onmessage = (event) => {
      const message: BackendMessage = JSON.parse(event.data);
      if (message.type === 'MISSION_STARTED') {
        setMissionPlan(message.plan);
        setError(null);
      } else if (message.type === 'MISSION_ERROR') {
        setError(message.error);
      } else if (message.type === 'TELEMETRY') {
        setTelemetry(message.payload);
      }
    };

    wsRef.current = ws;
    return () => ws.close();
  }, []);

  const startMission = useCallback((boundaryPoints: LatLng[]) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      setError('Not connected to backend');
      return;
    }
    wsRef.current.send(JSON.stringify({
      type: 'START_MISSION',
      payload: {
        field_id: 'field_alpha',
        boundary_points: boundaryPoints,
        row_spacing_m: 1.0,
        sampling_density_m: 3.0,
        active_payload: 'IRRIGATION',
        prescription: {},
      },
    }));
  }, []);

  const stopMission = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: 'STOP_MISSION' }));
  }, []);

  return { connected, missionPlan, telemetry, error, startMission, stopMission };
}
```

---

## Step 6 — Main App (`frontend/src/App.tsx`) (2 hrs)

**Bug fix vs. earlier draft:** the previous version rendered mission waypoints and the rover position using a bare `<circle>` JSX tag. That's an SVG element, not a component `@react-google-maps/api` exports — it will not render inside `<GoogleMap>`. Use the library's `Circle` and `Marker` components instead, as below.

```tsx
import { useState } from 'react';
import { LoadScript, GoogleMap, Polygon, Circle, Marker } from '@react-google-maps/api';
import { useMissionSocket } from './hooks/useMissionSocket';
import type { LatLng } from './types';
import MissionStatusPanel from './components/MissionStatusPanel';
import TelemetryPanel from './components/TelemetryPanel';
import ResourcesPanel from './components/ResourcesPanel';

const LIBRARIES: ('drawing' | 'places')[] = ['drawing', 'places'];
const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
const DEFAULT_CENTER: LatLng = { lat: 13.0827, lng: 80.2707 };

export default function App() {
  const [boundaryPoints, setBoundaryPoints] = useState<LatLng[]>([]);
  const [fieldSubmitted, setFieldSubmitted] = useState(false);
  const { connected, missionPlan, telemetry, error, startMission, stopMission } = useMissionSocket();

  const handleMapClick = (e: google.maps.MapMouseEvent) => {
    if (fieldSubmitted || !e.latLng) return;
    setBoundaryPoints((prev) => [...prev, { lat: e.latLng!.lat(), lng: e.latLng!.lng() }]);
  };

  const handleFinishField = () => {
    if (boundaryPoints.length < 3) {
      alert('Select at least 3 boundary points first.');
      return;
    }
    setFieldSubmitted(true);
    startMission(boundaryPoints);
  };

  const handleReset = () => {
    setBoundaryPoints([]);
    setFieldSubmitted(false);
    stopMission();
    window.location.reload(); // simplest reliable reset for a hackathon MVP
  };

  const roverPosition: LatLng | null = telemetry
    ? { lat: telemetry.gps_lat, lng: telemetry.gps_lng }
    : null;

  return (
    <LoadScript googleMapsApiKey={API_KEY} libraries={LIBRARIES}>
      <div className="min-h-screen bg-slate-50">
        <header className="bg-white border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            /* Lines 266-275 omitted */
          </div>
        </header>

        {error && (
          <div className="max-w-7xl mx-auto px-6 pt-4">
            /* Lines 280-283 omitted */
          </div>
        )}

        <main className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 p-4">
            /* Lines 288-360 omitted */
          </div>
        </main>
      </div>
    </LoadScript>
  );
}
```

---

## Step 7 — Panel Components (1 hr)

`frontend/src/components/MissionStatusPanel.tsx`:
```tsx
import type { MissionPlan } from '../types';

export default function MissionStatusPanel({ missionPlan }: { missionPlan: MissionPlan | null }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
      <h2 className="font-semibold text-slate-800 mb-3">Mission Status</h2>
      {missionPlan ? (
        <dl className="space-y-2 text-sm">
          /* Lines 382-387 omitted */
        </dl>
      ) : (
        <p className="text-sm text-slate-400">No active mission</p>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-mono text-slate-800">{value}</dd>
    </div>
  );
}
```

`frontend/src/components/TelemetryPanel.tsx`:
```tsx
import type { TelemetryData } from '../types';

const STATUS_COLOR: Record<string, string> = {
  NAVIGATING: 'text-emerald-600',
  COMM_LOST: 'text-red-600',
  LOW_BATTERY: 'text-red-600',
  STUCK: 'text-amber-600',
  ARRIVED_AT_NODE: 'text-blue-600',
  PERFORMING_ACTION: 'text-blue-600',
  MISSION_COMPLETE: 'text-emerald-600',
  IDLE: 'text-slate-500',
};

export default function TelemetryPanel({ telemetry }: { telemetry: TelemetryData | null }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
      <h2 className="font-semibold text-slate-800 mb-3">Live Telemetry</h2>
      {telemetry ? (
        <dl className="space-y-2 text-sm">
          /* Lines 426-459 omitted */
        </dl>
      ) : (
        <p className="text-sm text-slate-400">No telemetry received</p>
      )}
    </div>
  );
}
```

`frontend/src/components/ResourcesPanel.tsx`:
```tsx
import type { ResourcesUsed } from '../types';

export default function ResourcesPanel({ resources }: { resources: ResourcesUsed }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
      <h2 className="font-semibold text-slate-800 mb-3">Resources Used</h2>
      <dl className="space-y-2 text-sm">
        <div className="flex justify-between">
          /* Lines 478-488 omitted */
        </div>
      </dl>
    </div>
  );
}
```

---

## Step 8 — Design Notes (for the "visually polished / demo-ready" requirement)

- Palette: slate backgrounds, emerald for "good/active" states, amber for warnings, red for faults — already applied above via Tailwind utility classes.
- Keep the map at a fixed 500px height so the layout doesn't jump when a mission starts.
- The status pill in the header (`Backend connected` / `Backend offline`) is a cheap, high-value addition for judges — it visibly proves the WebSocket link is live before you even start clicking the map.
- Don't add animation libraries under time pressure; Tailwind's `transition` utility on buttons is enough polish for a 48-hour build.

---

## Step 9 — Testing Without Hardware (SW1 dependency check)

You can build and demo the entire map + mission-request flow before the ESP32 exists:

1. Start SW1's backend (`uvicorn main:app --reload`) — no ESP32 needs to be connected.
2. `npm run dev`, open `http://localhost:3000`.
3. Click 3–4 points on the map, click **Finish Field & Start Mission**.
4. Confirm the mission status panel populates (area, distance, waypoints) — this proves the WebSocket round-trip and path planner work end-to-end, independent of firmware.
5. To test the telemetry panel without a rover, temporarily point `VITE_BACKEND_WS_URL` at a small mock server, or ask SW1 for a `POST /api/mock-telemetry` debug endpoint if time allows (optional, not required for MVP).

---

## Step 10 — Self-Test Checklist Before Integration Hour

- [ ] `npm run build` completes with zero TypeScript errors
- [ ] Map renders, boundary clicking works, polygon overlay draws correctly
- [ ] `MISSION_STARTED` response populates the status panel with real numbers (not `NaN`/`undefined`)
- [ ] `MISSION_ERROR` (e.g. from clicking only 2 points then forcing a submit) shows the red error banner instead of crashing
- [ ] Waypoint markers (red circles) render on the map for a returned plan
- [ ] `.env.local` is gitignored and not present in `git status`
- [ ] Committed and pushed to `sw2/frontend`, PR opened against `main`
