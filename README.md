# ParkSpot AI

ParkSpot is a parking reservation service: ParkSpot establishes agreements with existing parking facilities and makes the capacity authorized under those agreements bookable by drivers. Drivers search by destination, compare real facilities (price, amenities, authorized spaces left for their time window), reserve through the backend, and enter participating facilities via QR pass or plate recognition. Cameras at partner facilities run detection/segmentation (SAM 2 in real mode) plus plate OCR (EasyOCR); entry grants are decided only by the backend's reservation matching. A Llama 3 assistant searches the same live inventory, and a dynamic pricing engine adjusts prices to demand, weather and events.

**Roles:** drivers self-register. Partner-operator (`host`) and `admin` accounts are provisioned by ParkSpot operations — there is no public partner sign-up or self-service marketplace listing. Facilities carry `total_capacity` (physical spaces) and `authorized_capacity` (spaces ParkSpot may sell); booking and search enforce the authorized capacity and revalidate it when a hold is submitted, so ParkSpot inventory can never be overbooked.

## Quick start

Easiest — one command from the repo root (creates the venv if missing, migrates, seeds, serves):

```bash
bash run.sh        # then open http://localhost:8000
```

Manual equivalent, using the bundled `.venv` (Python 3.12):

```bash
cd /home/asaaoud/Desktop/ParkSpot-AI
cp .env.example .env   # set SECRET_KEY (32+ chars); LLAMA_API_KEY / MAPBOX_ACCESS_TOKEN optional
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m scripts.seed
.venv/bin/python -m uvicorn app.main:app --port 8000
```

Fresh setup without the bundled venv: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt`, then the commands above.

Open http://localhost:8000 — demo logins: `driver@demo.test` / `host@demo.test` / `admin@demo.test`, password `demo1234`. Driver plate: `DEMO1234`. Cameras: `cam-001`…`cam-006`.

Without `LLAMA_API_KEY`, chat returns a degraded friendly reply and pricing uses the deterministic heuristic — the demo never hangs. Without a Mapbox token, the map shows a fallback message and search/list still work.

## Real vision mode

```bash
.venv/bin/python -m pip install -r requirements-vision.txt
VISION_MODE=real .venv/bin/python -m uvicorn app.main:app --port 8000
```

Simulate mode (default) needs no ML dependencies; SAM 2/EasyOCR/torch/cv2 are imported lazily only in real adapters.

## API

All routes under `/api/v1` (plus `GET /health`). Highlights: `POST /auth/register|login`, `GET /spots/search?lat&lng`, `POST /bookings/hold` → `POST /bookings/{id}/confirm` → `GET /bookings/{id}/qr`, `POST /chat`, `POST /pricing/recompute` (admin), `POST /vision/simulate`, `POST /access/verify-qr`, `GET /admin/stats`. Errors are `{"detail": "...", "code": "..."}`.

Alternative Llama providers are env-only: set `LLAMA_BASE_URL`/`LLAMA_MODEL` for Meta Llama API (default), Groq, Together AI, or Ollama (`http://localhost:11434/v1`, `llama3.1:8b`).

## Tests & demo

```bash
.venv/bin/python -m pytest -q
bash scripts/demo_flow.sh   # with server running after seed
.venv/bin/python -m scripts.simulate_camera --camera cam-001 --arrive DEMO1234
```

Architecture: FastAPI + SQLAlchemy 2.0 async (SQLite/WAL, Alembic) → services own authorization & commits, repositories never commit → Llama 3 tool-calling agent (user injected via `ToolContext`, never from the model) → APScheduler workers expire holds, mark no-shows, auto-complete, and refresh per-zone pricing snapshots.

## Frontend

Premium Light UI (default and only theme): map-first discovery with a synchronized results list on desktop, Map/List toggle and bottom tab bar on mobile, hold → review (price breakdown, hold expiry, cancellation terms) → confirm booking flow, My Bookings + Profile page, login/register with explicit Back-to-home and return-to-intended-destination (a reservation interrupted by login is resumed automatically), Llama 3 chat drawer with structured facility cards and optional Web Speech voice input (hidden where unsupported; text always works), a role-guarded Partner Operations area (facility capacity configuration + camera-simulator entry monitoring; access grants happen only server-side), and an admin console that separates observed stats from Llama/heuristic pricing snapshots. Installable as a PWA — the service worker caches only the static shell and never caches `/api/` responses, so availability, auth and bookings always come from the network.
