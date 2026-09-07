# SETUP_BASE.md — Autonomous Precision Agriculture Rover
### Initial Repository Setup & Team Synchronization

This file is Step 0. Everyone (HW1, HW2, SW1, SW2) runs through this once, together, before splitting into parallel tracks. Budget: 30–45 minutes.

---

## 1. Repository Structure

```
agri-rover/
├── backend/                  # SW1 owns this
│   ├── main.py
│   ├── path_planner.py
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/
│       └── test_path_planner.py
├── frontend/                 # SW2 owns this
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── types.ts
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
├── firmware/                 # HW2 + SW1 shared (contract only, not built by SW1)
│   └── esp32_main.ino
├── docs/
│   ├── SETUP_BASE.md
│   ├── SW1_BACKEND_INSTRUCTIONS.md
│   ├── SW2_FRONTEND_INSTRUCTIONS.md
│   └── INTEGRATION_TESTING.md
├── .gitignore
└── README.md
```

**Key rule:** SW1 never edits `frontend/`. SW2 never edits `backend/`. The only shared surface is the WebSocket/JSON schema defined in `README.md` §"Data Contracts" — treat that section as an interface contract that requires both people's sign-off to change.

---

## 2. GitHub Repository Init

Run once, by whoever is "repo owner" (pick one person, e.g. SW1):

```bash
mkdir agri-rover && cd agri-rover
git init
git branch -M main

mkdir -p backend/tests frontend/src/components firmware docs

cat > .gitignore << 'EOF'
# Python
__pycache__/
*.pyc
venv/
.env

# Node
node_modules/
dist/
.env.local

# IDE
.vscode/
.idea/
*.log

# OS
.DS_Store
EOF

git add .gitignore
git commit -m "chore: initial repo structure"
```

Create the GitHub repo (via `gh` CLI or the web UI), then:

```bash
git remote add origin https://github.com/<org>/agri-rover.git
git push -u origin main
```

---

## 3. Branch Strategy

Two long-lived feature branches, merged into `main` at each integration checkpoint (see §5 of the timeline in the master prompt — hours 18, 24, 36).

```bash
git checkout -b sw1/backend
git checkout main
git checkout -b sw2/frontend
```

Rules:
- Commit early, commit often, push at least every hour so nothing is lost.
- Never force-push to `main`.
- Open a PR into `main` at hour 18 (first integration test) even if the code isn't finished — merge conflicts are cheaper to resolve early and often than once.
- Rebase your feature branch on `main` right after each merge, don't let branches diverge for more than a few hours.

---

## 4. Environment Setup (Both Devs, Parallel)

### Python (SW1)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --upgrade pip
```
(Requirements file is created in SW1_BACKEND_INSTRUCTIONS.md step 1.)

### Node.js (SW2)
```bash
cd frontend
node --version   # confirm >= 18
npm create vite@latest . -- --template react-ts
```
(Full dependency install is in SW2_FRONTEND_INSTRUCTIONS.md step 1.)

---

## 5. Shared Configuration Everyone Must Agree On Now

Write these three values on a whiteboard/shared doc before splitting up — they're needed by both tracks and by firmware:

| Value | Default | Notes |
|---|---|---|
| Backend host:port | `0.0.0.0:8000` | FastAPI/Uvicorn |
| Frontend dev port | `3000` | Vite |
| Laptop IP on hackathon Wi-Fi | `192.168.1.100` (placeholder) | Confirm actual IP once the portable router is up; ESP32 firmware hardcodes this |

Also agree now: **row_spacing_m = 1.0**, **sampling_density_m = 3.0** — these are the MVP defaults baked into both the path planner and the frontend's mission request payload. Don't let them drift.

---

## 6. First Commit Checkpoint

Before splitting into parallel tracks, verify:
- [ ] Repo pushed to GitHub, both devs have push access
- [ ] Both devs have cloned and can run `git status` cleanly
- [ ] `backend/venv` activates without error
- [ ] `frontend` scaffold runs with `npm run dev` and shows the Vite default page
- [ ] Laptop IP for the hackathon Wi-Fi is known (or a placeholder is agreed, to be updated later)

Once all boxes are checked, SW1 proceeds to `SW1_BACKEND_INSTRUCTIONS.md` and SW2 proceeds to `SW2_FRONTEND_INSTRUCTIONS.md` — fully in parallel, no further sync needed until the hour-18 integration checkpoint.
