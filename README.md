# Welcome to your Lovable project

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Open your project in the [Lovable editor](https://lovable.dev) and keep building.

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: connect the project to GitHub and every change made in Lovable is committed straight to your repository.
- **Full ownership**: this code is yours. Push to your repository and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```

## Built with

- TanStack Start
- TypeScript
- React
- Tailwind CSS

## Meta AI integration (Muse Spark · SAM 3.1 · EasyOCR · Voice)

A FastAPI backend in [`app/meta/`](app/meta/) adds Meta-powered features.
All credentials live **only** in a backend `.env` (git-ignored; see
[`.env.example`](.env.example) for placeholders). Nothing secret is ever
sent to the frontend.

### Honest capability status (verified against Meta's public docs)

| Feature | Status |
|---|---|
| **Muse Spark assistant** | Implemented as an OpenAI-compatible Chat Completions client with controlled tool calling (`search_facilities`, `get_facility_details`, `check_availability`, `calculate_booking_quote`). Set `META_MODEL_API_KEY` + the exact `MUSE_SPARK_MODEL` identifier from your Meta developer account — Meta has not published a public Muse Spark developer model id, so none is hardcoded or invented. Without them the endpoint returns `not_configured` and the app's existing assistant/search keep working. |
| **SAM 3.1 vision** | Meta ships SAM 3/3.1 as **open weights** ([facebookresearch/sam3](https://github.com/facebookresearch/sam3), `facebook/sam3` on Hugging Face) — there is no Meta-hosted SAM cloud API key. Deploy the weights to your own inference service, set `SAM_SERVICE_URL` (and `SAM_MODEL`), and the ops camera panel works. SAM only *locates* vehicles/plates; it never reads text and never grants access alone. |
| **EasyOCR plates** | Separate OCR step (optional, `requirements-vision.txt`). Reads below `OCR_MIN_CONFIDENCE` are rejected; access requires a matching real booking in the database. |
| **Muse Voice Transcribe** | Voice search implemented per project spec: `POST /api/v1/voice/transcribe`, `META_VOICE_BASE_URL` (default `https://api.meta.ai/v1`), model from `MUSE_VOICE_MODEL` (default `muse-voice-transcribe-1.0`), multipart `request` JSON (`PUSH_TO_TALK`, language bias Arabic/French/English) + mono 16 kHz WAV audio. Browser WebM/M4A is converted with FFmpeg on the backend; recordings capped at 30 s / 10 MB, never stored or logged. **Off by default** (`MUSE_VOICE_ENABLED=true` + `MODEL_API_KEY` to enable). Darija recognition is not promised — transcripts are shown for editing first. These Meta endpoint/model values come from the project specification and should be confirmed in your Meta developer account before going live. |
| **GPS nearby parking** | "Parking Near Me" on Home: explicit-tap foreground browser geolocation (never on launch, never tracked/stored), Haversine ranking over real facility coordinates, radius 5 km default (widen up to 50 km), distances shown on cards. Backend twin: `GET /api/v1/meta/spots/nearby` and a `search_nearby_facilities` assistant tool that only works with device-shared coordinates — the model can never supply or guess GPS. |

### Run the backend

```sh
pip install -r requirements-meta.txt        # core (light)
pip install -r requirements-vision.txt      # optional EasyOCR (heavy, torch)
cp .env.example .env                        # fill in your keys — never commit
uvicorn app.meta.api:app --port 8000 --host 0.0.0.0   # auto-loads ./.env; 0.0.0.0 = reachable from a phone on the LAN
```

Point the frontend at it with a public (non-secret) URL:

```sh
VITE_META_API_URL=http://localhost:8000 npm run dev
```

Endpoints: `GET /api/v1/meta/status` (flags only), `POST /api/v1/meta/assistant/chat`,
`POST /api/v1/meta/vision/analyze` (partner/admin), `POST /api/v1/meta/voice/transcribe`.
Every route verifies the caller's own Supabase JWT; the model can only call
validated tools over real inventory, and prices are computed server-side in
integer cents — the model never invents facilities, prices, permissions, or access.

## Super Admin Control Center

Admins (users with the `admin` role in `user_roles`) get a full control
center at `/admin`, linked from Operations. The FastAPI backend exposes
`/api/v1/admin/*` and re-verifies the admin role **server-side on every
request** using the caller's own Supabase JWT. The admin RLS policies in
`drizzle/migrations/0001_admin.sql` are the second layer, so no
service-role key exists anywhere in this project.

**One-time setup:** run [`drizzle/migrations/0001_admin.sql`](drizzle/migrations/0001_admin.sql)
in the Supabase SQL Editor. Until then, admin endpoints return database
errors because the `audit_logs`, `cameras`, `incidents`, and `app_settings`
tables, the capacity columns, and the admin policies do not exist yet.

Sections: Overview (real counts, bookings-per-day chart, status mix),
Users & Accounts (search, suspend/reactivate, grant/revoke roles),
Parking Facilities (create/edit, activation toggle), Bookings (filter,
cancel with the standard refund policy), Pricing (price edits within
configured bounds, change history), AI Management (configured/model
visibility, safe reachability health checks, runtime feature toggles),
Cameras & Access (camera registry + recent verification events),
Payments & Wallet (DEMO — adjustments only through the
`admin_adjust_wallet` database function, never direct balance writes),
Reports (7/30/90-day summaries + audited CSV export), Notifications
(incident queue), Audit Logs (append-only, filterable), and System
Settings (allow-listed keys only — no secrets, no SQL, no shell).

Safety rules enforced server-side: authorized capacity never exceeds
total physical capacity and never drops below active reservations; the
last administrator cannot be suspended or demoted and nobody can suspend
themselves; every sensitive action requires a reason (min 3 chars) and
writes an audit entry; money moves only inside SECURITY DEFINER
functions, in the same transaction as its audit row. Suspension blocks
the account across the ParkSpot backend immediately; fully revoking live
Supabase sessions would require a service-role key, which this project
deliberately does not use.

### Tests

```sh
pytest tests/test_meta_integration.py -q   # mocked transports — no credentials needed
pytest tests/test_admin.py -q              # admin API: authz, capacity, audit, settings
npm test                                    # frontend unit tests
```
