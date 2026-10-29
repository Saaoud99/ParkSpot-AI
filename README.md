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
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Using it on your phone ("127.0.0.1 refused to connect")

There is no separate mobile app build: the phone browser / installed PWA loads the same FastAPI-served frontend, and the frontend calls the API with same-origin relative URLs (`/api/v1`). `127.0.0.1` always means "this device" — on a phone it is the phone itself, where nothing is listening, hence the refusal. To use ParkSpot on a phone:

1. Start the server with `bash run.sh` (it binds `0.0.0.0` and prints the LAN URL, e.g. `http://192.168.1.20:8000`).
2. Connect the phone to the same Wi-Fi and open that LAN URL — not `127.0.0.1` or `localhost`.
3. Android Emulator: use `http://10.0.2.2:8000` (the emulator's alias for the host machine). iOS Simulator shares the host network, so `http://localhost:8000` works there.
4. If the OS firewall blocks inbound port 8000, allow it for your private network.

Notes: service-worker/PWA install requires a secure context (HTTPS or `localhost`), so over a plain-HTTP LAN address the app runs fully in the browser but may not offer "Install". CORS only matters if you deliberately host the frontend separately from the API; in that case set `window.__PARKSPOT_API_BASE__` (see [frontend/js/api.js](frontend/js/api.js)), add that frontend origin to `CORS_ORIGINS` in `.env`, and extend the CSP `connect-src` in [app/main.py](app/main.py) to match — do not use `*`.

Fresh setup without the bundled venv: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt`, then the commands above.

Open http://localhost:8000 — demo logins: `driver@demo.test` / `host@demo.test` / `admin@demo.test`, password `demo1234`. Driver plate: `DEMO1234`. Cameras: `cam-001`…`cam-006`.

Without `LLAMA_API_KEY`, chat immediately returns an honestly-labelled degraded reply (never presented as Llama output) and pricing uses the deterministic heuristic — the demo never hangs. Without a Mapbox token, the map shows a fallback message and search/list still work.

## Honest capability status

| Capability | Status in this repo |
|---|---|
| Search, holds, confirmation, cancellation | **Working** — server revalidates authorized capacity at hold time; expired holds claim no capacity; prices are locked at hold and never silently change at confirmation. |
| Payments | **Mock provider only** — confirming records a mock payment; no real card is charged. The UI says so at confirmation. A production deployment must integrate a real PSP and authorize payment before confirmation. |
| Llama assistant | **Real when configured, degraded otherwise** — with `LLAMA_API_KEY` set, the assistant uses server-side tools over live inventory; the model is never the authority for availability, price, identity, or access. Without a key it replies with a clearly-labelled unavailable message. |
| Dynamic pricing | **Heuristic + optional Llama suggestion** — multipliers are computed from observed occupancy/bookings, hour, live Open-Meteo weather, and admin-entered events; Llama (when configured) only suggests a multiplier the server clamps. `pricing_source` is shown to users/admins. It is not a trained ML model. |
| Vision — simulate (default) | **Simulated detection/OCR, real backend matching** — presence/plate are synthetic inputs; the grant decision (booking, facility, window, plate, confidence) is the real server pipeline. |
| Vision — real (`VISION_MODE=real`) | **Unverified without weights/deps** — requires `requirements-vision.txt`, a loadable SAM 2 checkpoint, and EasyOCR. Missing deps/weights now fail loudly (`vision_unavailable`) instead of silently simulating. SAM 2 only segments the vehicle; EasyOCR reads the plate; the backend still decides. |
| Facility photos | **None bundled** — no genuine photos exist in the repo, so cards/detail pages show a labelled placeholder rather than stock photos presented as real facilities. |
| Entry (QR / plate) | **Working with replay protection** — QR passes are signed, bound to one booking, single-check-in, and revoked on cancellation; low-confidence OCR reads are denied (QR remains the fallback). |

## Security posture & remaining production work

Implemented: bcrypt password hashing, generic login errors, JWT access/refresh tokens with type checks, server-side role + ownership enforcement on every protected route (drivers/hosts/admins, cross-user booking & QR tests included), authorized-capacity revalidation with per-facility hold serialization, single-use QR passes, rate limits on auth/chat/camera frames, camera upload size/type/dimension validation, security headers (CSP, `nosniff`, frame denial, `no-store` on API), restricted CORS, sanitized validation errors (submitted passwords are never reflected), and prod fail-closed checks (unique `SECRET_KEY`, `DEBUG=false`).

Not done / required before real production: a real payment provider; TLS termination + HSTS at the edge; a distributed rate limiter and DB (Postgres with row locks instead of the in-process hold lock); refresh-token rotation/revocation and server-side logout; per-camera credentials instead of the shared camera key; genuine facility photography; load testing of real SAM 2/EasyOCR on target hardware. Bearer tokens are stored in `localStorage` by the shell — mitigated by strict output escaping, but an HttpOnly-cookie session is the stronger production design.

## Real vision mode

```bash
.venv/bin/python -m pip install -r requirements-vision.txt
VISION_MODE=real .venv/bin/python -m uvicorn app.main:app --port 8000
```

Simulate mode (default) needs no ML dependencies; SAM 2/EasyOCR/torch/cv2 are imported lazily only in real adapters. Real mode additionally requires a SAM 2 checkpoint the `sam2` package can load via the configured `SAM2_MODEL_ID`; if it cannot load, frame processing returns a clear `vision_unavailable` error rather than falling back to simulation.

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

Premium Light UI (default and only theme): map-first discovery with a synchronized results list on desktop (price/distance/spaces sorting, facility-type + covered/EV/price filters), a facility detail page (`/spot.html?id=…`) with live spaces-left, pricing note, directions and terms, Map/List toggle and bottom tab bar on mobile, hold → review (price breakdown, hold expiry, cancellation terms, explicit demo-payment disclosure) → confirm booking flow, My Bookings with upcoming/completed/cancelled tabs plus editable Profile and vehicle management, login/register with explicit Back-to-home and return-to-intended-destination (a reservation interrupted by login is resumed automatically), Llama chat drawer with structured facility cards and optional Web Speech voice input (hidden where unsupported; text always works), a role-guarded Partner Operations area (facility capacity configuration + camera-simulator entry monitoring; access grants happen only server-side), and an admin console that separates observed stats from Llama/heuristic pricing snapshots. Installable as a PWA — the service worker caches only the static shell and never caches `/api/` responses, so availability, auth and bookings always come from the network.

Brand identity: a single SVG mark — a white location pin with a "P" cut into its head on a deep-green (`#0B6E3D` → emerald) rounded square — lives at [frontend/icon.svg](frontend/icon.svg) and is used as favicon, PWA icon (any + maskable), splash-screen mark, header wordmark lockup on every page, auth-page brand block, and chat avatar. Tagline: "Smarter parking, easier journeys". The home page shows a brief (~0.65s, non-blocking, reduced-motion-safe) branded splash on load. Raster PNG icons are not bundled; modern browsers accept the SVG PWA icon, and a PNG set can be exported from the SVG for stores that require it.
