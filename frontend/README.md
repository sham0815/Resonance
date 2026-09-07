# AgriRover dashboard

## Run locally

```bash
npm install
copy .env.example .env.local
npm run dev
```

Set `VITE_BACKEND_WS_URL` in `.env.local`. The map uses OpenStreetMap tiles through Leaflet and does not require a map API key. The dashboard sends `START_MISSION` over `/ws/frontend` and consumes `MISSION_STARTED`, `MISSION_ERROR`, and `TELEMETRY` without implementing planner logic in the browser.
