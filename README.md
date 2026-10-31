# ParkSpot AI — Smarter Parking. Easier Journeys.

> Find, book and pay for parking in Morocco — in seconds, from your phone.

ParkSpot AI is a mobile-first parking platform for Moroccan cities
(Casablanca, Rabat, Marrakech, Tangier, …). A driver opens the app, sees
**real** parking facilities with **live availability and prices in MAD**,
books a spot, pays from the built-in **ParkSpot Wallet**, and gets an
access code — with an AI assistant, a live map, GPS “Parking Near Me”,
and voice search on top. Parking operators (partners) manage their
capacity, and administrators run the whole platform from a Super Admin
Control Center.

This README is the single entry point to the project: what it is, how it
is built, how to run it, how the environment works, and where everything
lives. If you only read one document, read this one.

---

## Table of contents

- [The idea](#the-idea)
- [Who it is for](#who-it-is-for)
- [Features](#features)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [How to use the app](#how-to-use-the-app)
- [Screens & routes](#screens--routes)
- [Backend API](#backend-api)
- [Database & money rules](#database--money-rules)
- [Internationalisation (EN / AR, RTL)](#internationalisation-en--ar-rtl)
- [App shell & scrolling](#app-shell--scrolling)
- [Meta AI integration — honest status](#meta-ai-integration--honest-status)
- [Super Admin Control Center](#super-admin-control-center)
- [Live demo script (hackathon)](#live-demo-script-hackathon)
- [Known limitations](#known-limitations)
- [Tests](#tests)
- [Build, lint & deployment notes](#build-lint--deployment-notes)
- [Troubleshooting](#troubleshooting)
- [Security rules (do not break these)](#security-rules-do-not-break-these)
- [Working with Lovable](#working-with-lovable)

---

## The idea

Finding parking in a dense city centre is slow, uncertain and cash-based:
you circle the block, you don't know the price, you don't know if a space
is even free. ParkSpot AI fixes the three uncertainties before you leave:

1. **Where** — every partner facility is on a list and a live map, with
   its address, city and GPS coordinates.
2. **Whether** — each facility shows real remaining capacity against its
   **authorised** capacity (`available / authorised`), updated when
   bookings are made or cancelled. Deactivated facilities disappear
   from driver search entirely.
3. **How much** — the price per hour is shown up front, and the total is
   computed **on the server** from that price. You pay from a prepaid
   wallet in the app — no cash, no surprise price at the barrier.

The business model is **partner facilities with authorised capacity**:
ParkSpot does not invent parking spaces. A facility's *total* capacity is
physical; only its *authorised* capacity can be sold through ParkSpot,
and it can never exceed the total or drop below active reservations.

## Who it is for

| Persona | What they do in the app |
|---|---|
| **Driver** (`user`) | Discover parking, book, pay with the wallet, cancel with a refund, ask the AI assistant, use voice/GPS search. |
| **Partner / operator** (`partner`) | Operations screen (`/ops`): see bookings & revenue, correct live availability, run the camera/vision check. |
| **Administrator** (`admin`) | Everything a partner can do, plus the Super Admin Control Center (`/admin`) and admin API. |

Roles live in the `user_roles` table (`admin` / `partner` / `user`) and
are checked in the database (RLS), in the frontend, **and** again on the
backend for every admin request.

## Features

**For drivers**

- 🏠 **Home / discovery** — search by name/city/address, city filter
  chips (Casablanca, Rabat, Marrakech, Tangier), facility cards with
  photo, rating, price/hour and live availability.
- 📍 **Parking Near Me** — explicit-tap GPS (never on launch, never
  tracked or stored): Haversine ranking over real facility coordinates,
  5 km radius by default, widen up to 50 km, distances on the cards.
- 🗺️ **Live map** (`/map`) — Leaflet/OpenStreetMap map with price pins;
  tap a pin (or a card in the bottom rail) to open the facility.
- 📅 **Booking** — pick a facility, start time and 1–24 hours; the server
  computes the total, reserves one space and returns an **access code**.
- 👛 **ParkSpot Wallet (DEMO money)** — prepaid balance in MAD, demo
  top-up, reserved/available amounts, full transaction history.
  Cancellation refund policy: **≥ 2 h before start → 100 %**,
  **< 2 h before start → 50 %**, **after start → 0 %**.
- 🤖 **AI assistant** (`/assistant`) — ask where to park, prices, wallet
  questions. It can only call validated tools over real inventory and
  renders cards only for facilities that actually exist — it never
  invents facilities, prices, permissions or access. With Meta
  credentials configured it runs Muse Spark; without them it runs an
  honestly-labeled **grounded fallback** (deterministic search over the
  same real inventory — the UI badge tells you which mode answered).
- 🎙️ **Voice search** — record up to 30 s; the transcript lands in the
  search box for editing first. Saying “near me / قريب مني / près de moi”
  also triggers the GPS flow. (Backend feature, off by default.)
- 🌍 **English + Arabic with full RTL** — every string goes through
  `t()` in `src/lib/i18n.tsx`; layout mirrors in Arabic.

**For partners & admins**

- 🛠️ **Operations** (`/ops`) — bookings count, revenue, per-facility
  availability correction, camera panel (SAM 3.1 detection + EasyOCR
  plate read; access is granted **only** when the plate matches a real
  booking — vision alone never opens a barrier).
- 👑 **Super Admin Control Center** (`/admin`) — see
  [its section below](#super-admin-control-center).

## Tech stack

| Layer | Technology |
|---|---|
| Web app | React 19, TypeScript, TanStack Start (SSR) + TanStack Router (file-based routes), TanStack Query |
| Styling | Tailwind CSS v4, shadcn/ui (Radix), Lucide icons, Fraunces + Plus Jakarta Sans + Noto Kufi Arabic |
| Map | Leaflet + OpenStreetMap tiles |
| Database / Auth | Supabase (Postgres, Row Level Security, `SECURITY DEFINER` SQL functions, JWT auth, Google OAuth) |
| AI / vision backend | FastAPI (Python) in `app/meta/` — Muse Spark tool-calling, SAM 3.1 (self-hosted), EasyOCR, Muse Voice, grounded fallback assistant |
| Chat fallback (no backend) | TanStack server route `src/routes/api/chat.ts` — grounded replies from real Supabase inventory, rate-limited, no LLM |
| Tests | Vitest + Testing Library (frontend), pytest (backend) |
| Build | Vite (via `@lovable.dev/vite-tanstack-config`, Nitro), npm or Bun |

## Project structure

```
ParkSpot-AI/
├── README.md                  ← you are here
├── AGENTS.md                  ← project rules (wallet/money, i18n, Lovable)
├── .env.example               ← backend env template (placeholders only)
├── .env                       ← YOUR local secrets — git-ignored, never commit
├── package.json               ← frontend scripts & dependencies
├── vite.config.ts             ← Vite/TanStack config (Lovable preset — read its header!)
├── requirements-meta.txt      ← backend core deps (light, no torch)
├── requirements-vision.txt    ← optional EasyOCR deps (heavy, torch)
│
├── src/                       ← WEB APP (TanStack Start)
│   ├── routes/                ← file-based routes = the screens (see table below)
│   │   ├── __root.tsx         ← root layout: providers, fonts, <Outlet/>
│   │   ├── index.tsx          ← "/" splash + onboarding
│   │   ├── home.tsx           ← "/home" discovery, search, GPS, voice
│   │   ├── map.tsx            ← "/map" Leaflet map
│   │   ├── facility.$id.tsx   ← "/facility/:id" details
│   │   ├── book.$id.tsx       ← "/book/:id" booking form
│   │   ├── booking.$id.tsx    ← "/booking/:id" booking detail / access code
│   │   ├── bookings.tsx       ← "/bookings" my bookings (+ cancel/refund)
│   │   ├── wallet.tsx         ← "/wallet" balance + recent transactions
│   │   ├── topup.tsx          ← "/topup" demo top-up
│   │   ├── transactions.tsx   ← "/transactions" full history
│   │   ├── assistant.tsx      ← "/assistant" AI chat
│   │   ├── auth.tsx           ← "/auth" sign in / sign up / Google
│   │   ├── profile.tsx        ← "/profile" profile, vehicle, language
│   │   ├── ops.tsx            ← "/ops" partner operations + vision panel
│   │   ├── admin.tsx          ← "/admin" Super Admin Control Center
│   │   └── api/chat.ts        ← grounded chat server route (no LLM, rate-limited)
│   ├── components/
│   │   ├── AppShell.tsx       ← Phone frame + header + pinned bottom nav (scroll owner)
│   │   ├── FacilityCard.tsx   ← facility card (list / compact / with distance)
│   │   ├── ParkingMap.tsx     ← Leaflet map (lazy-loaded)
│   │   ├── TxRow.tsx          ← one wallet transaction row
│   │   └── ui/                ← shadcn/ui primitives (do not hand-edit casually)
│   ├── lib/
│   │   ├── i18n.tsx           ← ALL UI strings (en + ar) + language provider — use t()
│   │   ├── data.ts            ← facilities/wallet/transactions queries, mad() formatter
│   │   ├── geo.ts             ← geolocation (once, foreground) + Haversine distance
│   │   ├── meta.ts            ← client for the FastAPI backend (VITE_META_API_URL)
│   │   ├── assistantCore.ts   ← grounded fallback reply engine (real inventory only)
│   │   ├── admin.ts           ← client for /api/v1/admin/*
│   │   ├── auth.tsx           ← Supabase auth provider, roles, error mapping
│   │   └── utils.ts           ← cn() and helpers
│   ├── integrations/supabase/ ← generated Supabase client & auth plumbing
│   ├── styles.css             ← design system (oklch tokens) + .app-scroll / .no-scrollbar
│   ├── router.tsx / server.ts / start.ts
│   └── test/                  ← Vitest setup + routing/auth/assistant-core tests
│
├── app/meta/                  ← BACKEND (FastAPI) — the only Python package served
│   ├── api.py                 ← app factory, CORS, rate limit, /api/v1/meta/* + admin router
│   ├── admin.py               ← /api/v1/admin/* (role re-verified server-side per request)
│   ├── config.py              ← Settings.from_env() — all backend env vars
│   ├── auth.py                ← verifies the caller's own Supabase JWT
│   ├── inventory.py           ← real facilities/bookings access (Supabase REST)
│   ├── tools.py               ← assistant tools: search/details/availability/quote/nearby
│   ├── geo.py                 ← coordinate validation + nearby ranking
│   ├── access.py              ← vision → OCR → booking-verification pipeline
│   ├── flags.py / errors.py / metrics.py
│   └── services/
│       ├── muse_spark.py      ← Muse Spark chat (OpenAI-compatible, tool calling)
│       ├── grounded.py        ← grounded fallback assistant (no credentials needed)
│       ├── sam_vision.py      ← SAM 3.1 client (your self-hosted inference service)
│       ├── easy_ocr.py        ← EasyOCR plate reading (confidence-gated)
│       └── muse_voice.py      ← Muse Voice transcription (FFmpeg → 16 kHz WAV)
│
├── drizzle/migrations/
│   ├── 0000_migration.sql     ← core schema: profiles, roles, facilities, wallets,
│   │                            bookings, transactions + demo_topup/create_booking/cancel_booking
│   ├── 0001_admin.sql         ← admin: audit_logs, cameras, incidents, app_settings,
│   │                            capacity columns, admin_adjust_wallet, admin RLS policies
│   └── 0002_booking_capacity_guard.sql
│                              ← booking functions enforce `active` + authorised capacity
├── scripts/
│   ├── setup_new_db.sql       ← pointer to the canonical migration order (0000→0001→0002)
│   └── seed_demo_users.sql    ← demo accounts/seed helpers
├── supabase/config.toml       ← local Supabase config
├── tests/
│   ├── test_meta_integration.py ← Meta backend (mocked transports, no credentials needed)
│   ├── test_admin.py            ← admin API: authz, capacity, audit, settings
│   └── test_grounded.py         ← grounded fallback assistant over fake inventory
└── public/                    ← static assets (favicon, …)
```

> Note: `app/` also contains `__pycache__` folders from other historical
> Python packages whose sources are no longer in the repo. The backend
> that actually runs is **`app.meta.api:app`** only.

## Quick start

### Prerequisites

- **Node.js 20+** and npm (or Bun) — [install Node with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)
- **Python 3.11+** — only if you run the AI/admin backend
- A **Supabase project** (the app's database + auth)
- **FFmpeg** on the backend machine — a required *system* dependency if
  voice is enabled (it converts browser WebM/MP4 recordings to WAV; it is
  not a pip package and cannot come from `requirements-meta.txt`).
  Install: `sudo apt-get install ffmpeg` (Debian/Ubuntu) or
  `brew install ffmpeg` (macOS). Without it, voice stays honestly
  unavailable while everything else works.

### 1 — Frontend (the app itself)

```sh
git clone <this-repository-url>
cd ParkSpot-AI
npm install            # or: bun install
npm run dev            # Vite dev server (port/host printed in the terminal)
```

Open the printed URL. The app is a phone-shaped frame: on desktop it is
centred at max 440 px wide; on a phone it fills the screen.

### 2 — Supabase (database + auth) — required

The frontend talks directly to Supabase for auth, facilities, wallets and
bookings, so a project must exist and be migrated:

1. Create a project at [supabase.com](https://supabase.com) (or open the
   connected Lovable Cloud project).
2. In the **SQL Editor**, run, in order:
   - [`drizzle/migrations/0000_migration.sql`](drizzle/migrations/0000_migration.sql)
     — core tables, RLS, the three money functions, and 6 seeded
     facilities (Casablanca ×3, Rabat, Marrakech, Tangier). This alone
     is enough for the driver app (discovery, booking, wallet).
   - [`drizzle/migrations/0001_admin.sql`](drizzle/migrations/0001_admin.sql)
     — audit logs, cameras, incidents, settings, capacity columns
     (`total_capacity` / `authorized_capacity` / `active`) and admin
     policies. **Required for `/admin` and for the FastAPI backend** —
     the backend inventory selects the capacity columns, so without
     0001 its facility lookups fail honestly with
     `ProviderUnavailable`.
   - [`drizzle/migrations/0002_booking_capacity_guard.sql`](drizzle/migrations/0002_booking_capacity_guard.sql)
     — replaces `create_booking` / `cancel_booking` so bookings reject
     deactivated facilities (`FACILITY_INACTIVE`), never exceed
     authorised capacity, and cancellations restore availability only
     up to authorised capacity. Additive: it changes no data.
   - Optionally [`scripts/seed_demo_users.sql`](scripts/seed_demo_users.sql)
     for demo users.
3. Copy your project URL + publishable key into the frontend env (next
   section). New accounts are auto-confirmed by the seeded
   `handle_new_user` trigger, which also creates their profile, wallet
   and `user` role.

### 3 — Backend (optional, for AI / vision / voice / admin)

The app fully works without it (discovery, booking, wallet). The backend
adds the Muse Spark assistant tools, vision, voice and the admin API.
It requires migration `0001` (above). With **no Meta credentials at
all**, the assistant still answers in **grounded fallback mode** —
deterministic search over real inventory, clearly labeled in the UI
(`mode: "grounded_fallback"`) and never presented as LLM output. If
Muse Spark is configured but the provider fails, the assistant
degrades to the same grounded mode instead of erroring.

```sh
pip install -r requirements-meta.txt        # core (light)
pip install -r requirements-vision.txt      # optional EasyOCR (heavy, torch)
# Voice only: FFmpeg is a required SYSTEM dependency (not pip) —
#   sudo apt-get install ffmpeg   /   brew install ffmpeg
# Verify with: ffmpeg -version   (backend refuses non-WAV audio without it)
cp .env.example .env                        # fill in your keys — never commit
uvicorn app.meta.api:app --port 8000 --host 0.0.0.0
#   auto-loads ./.env; 0.0.0.0 = reachable from a phone on the same LAN
```

Then point the frontend at it (public URL, not a secret):

```sh
VITE_META_API_URL=http://localhost:8000 npm run dev
```

**Test on a real phone:** run both servers with `--host 0.0.0.0`, then
open `http://<your-LAN-IP>:<vite-port>` on the phone and set
`VITE_META_API_URL=http://<your-LAN-IP>:8000`. Note: microphone and GPS
require a secure context (HTTPS or `localhost`) in most browsers — over
a plain-HTTP LAN IP they are unavailable and the app says so honestly.

## Environment variables

There are **two different environments**. Mixing them up is the most
common setup mistake.

### Frontend — public, build-time (`VITE_*`)

Set these in your shell or a local env file before `npm run dev`. They
are compiled into the JS bundle, so they must **never be secrets**.

| Variable | Required | Example | What it does |
|---|---|---|---|
| `VITE_SUPABASE_URL` | ✅ | `https://xyz.supabase.co` | Supabase project URL (public). Server-side fallback name: `SUPABASE_URL`. |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | ✅ | `sb_publishable_…` | Supabase **publishable** key (safe to expose; RLS protects the data). Fallback: `SUPABASE_PUBLISHABLE_KEY`. |
| `VITE_META_API_URL` | for AI/admin | `http://localhost:8000` | Base URL of the FastAPI backend. Unset = backend features report “not connected” and the rest of the app keeps working. |

### Backend — secret, server-only (`.env`)

Copy [`.env.example`](.env.example) to `.env` on the backend machine
only. `.env` is git-ignored. **Nothing here may ever appear in frontend
code, HTML, JS bundles or API responses** — the backend only ever
returns feature *flags*, never keys.

| Variable | Default | What it does |
|---|---|---|
| `MODEL_API_KEY` | — | Meta Model API key (Muse Spark + voice). Backend only. |
| `META_BASE_URL` | `https://api.meta.ai/v1` | Meta Model API base URL. |
| `MUSE_SPARK_MODEL` | *(none, intentionally)* | **Exact** chat model id from your Meta developer account. No public id is published by Meta, so none is hardcoded — inventing one would fake the integration. Unset → the assistant runs in honestly-labeled grounded fallback mode over real inventory. |
| `SAM_SERVICE_URL` / `SAM_MODEL` / `SAM_SERVICE_API_KEY` | — | Your self-hosted SAM 3.1 inference service (`POST /segment`). Meta ships SAM as open weights — there is no Meta-hosted SAM API key. |
| `MUSE_VOICE_ENABLED` | `false` | Master switch for voice transcription. |
| `META_VOICE_API_KEY` / `META_VOICE_BASE_URL` / `MUSE_VOICE_MODEL` | `…/v1` / `muse-voice-transcribe-1.0` | Voice endpoint + model (confirm in your Meta account before going live). |
| `MUSE_VOICE_MAX_SECONDS` / `MUSE_VOICE_MAX_UPLOAD_MB` | `30` / `10` | Recording caps from one backend source: the API read limit and the service size check both derive from the upload cap, every accepted recording is validated/converted to mono 16 kHz WAV trimmed to the duration cap, and the frontend recording limit follows `voice_max_seconds` from `/api/v1/meta/status` (30 s default). Requires FFmpeg on the backend (see Prerequisites). Never stored or logged. |
| `NEARBY_SEARCH_DEFAULT_RADIUS_KM` / `NEARBY_SEARCH_MAX_RADIUS_KM` | `5` / `50` | GPS nearby-search radius bounds. |
| `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` | — | Same Supabase project as the frontend; the backend uses it **with the caller's own JWT** (no service-role key is configured or used in this project). |
| `META_TIMEOUT_S` / `META_MAX_RETRIES` / `META_RATE_LIMIT_PER_MINUTE` | `30` / `2` / `30` | Provider timeout, retries, per-user rate limit. |
| `OCR_MIN_CONFIDENCE` | `0.6` | Plate reads below this confidence are rejected. |
| `META_CORS_ORIGINS` | `*` | Comma-separated CORS allow-list. Tighten in production. |

## How to use the app

**As a driver (2 minutes):**

1. Open `/` → splash → onboarding → **Explore** (or sign up).
2. On **Home**, browse facilities, filter by city, or tap
   **Parking Near Me** and allow location.
3. Tap a facility → check price, availability against authorised
   capacity, and features → **Book this spot**.
4. Choose start time + hours (1–24). The total is computed server-side.
5. No balance? You will be sent to **Wallet → Add money (demo top-up)**.
   Top up, come back, confirm — one space is reserved and you get an
   **access code** (also under **Bookings**).
6. Need to cancel? **Bookings → Cancel**: full refund ≥ 2 h before
   start, 50 % after that, none after start. The space goes back on sale.
7. Ask the **Assistant** (“cheap parking near Casa Marina?”), tap the
   🎙️ mic on Home to search by voice, or open the **Map** to pick by pin.
8. Switch language any time in **Profile** (English ⇄ العربية, full RTL).

**As a partner:** sign in with a `partner`/`admin` account → **Profile →
Operations** (`/ops`) → correct a facility's live availability, review
bookings/revenue, and use **Cameras & Access** to analyse a camera frame
(upload or simulated). Access is “verified” only if the read plate
matches a real booking.

**As an admin:** **Operations → Admin Control Center** (`/admin`) — see
below. Grant roles from **Users & Accounts**; every sensitive action
needs a reason (min 3 chars) and is written to the audit log.

## Screens & routes

File-based routing: each file in `src/routes/` is a URL.
`routeTree.gen.ts` is generated — never edit it by hand.

| Route | Screen |
|---|---|
| `/` | Splash + 3-step onboarding (language toggle, skip) |
| `/home` | Discovery: search, city chips, GPS nearby, voice search, wallet/assistant shortcuts |
| `/map` | Leaflet map with price pins + facility rail |
| `/facility/:id` | Facility details, availability bar, features, sticky Book button |
| `/book/:id` | Booking form (date/time, hours, server-priced summary) |
| `/booking/:id` | Booking confirmation/detail with access code |
| `/bookings` | My bookings, access codes, cancel + refund |
| `/wallet` | Wallet balance (available/reserved/deposited), demo badge, recent transactions |
| `/topup` | Demo top-up |
| `/transactions` | Full wallet transaction history |
| `/assistant` | AI assistant chat (Meta backend; grounded fallback — mode badge shown) |
| `/auth` | Sign in / sign up / Google OAuth |
| `/profile` | Profile, vehicle plate/model, language, sign out, Operations link |
| `/ops` | Partner operations + SAM/EasyOCR camera panel |
| `/admin` | Super Admin Control Center (full-width, outside the phone frame) |
| `/api/chat` | Server route: grounded chat fallback (real inventory, rate-limited, no LLM) |

## Backend API

Base: `VITE_META_API_URL` (e.g. `http://localhost:8000`). Every route
verifies the caller's own Supabase JWT; identity never comes from the
request body or the model.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/meta/status` | public | Feature flags only (`assistant`: `"meta"` or `"grounded_fallback"`, `voice`, …) — never secrets or model keys. |
| `POST /api/v1/meta/assistant/chat` | user | Muse Spark with controlled tools: `search_facilities`, `get_facility_details`, `check_availability`, `calculate_booking_quote`, `search_nearby_facilities` (device-shared coordinates only — the model can never supply GPS). When Muse is unconfigured or unavailable it answers in grounded fallback mode over the same tools and says so (`mode` field + UI badge). |
| `POST /api/v1/meta/vision/analyze` | partner/admin | SAM 3.1 detection → EasyOCR plate → booking verification. |
| `POST /api/v1/voice/transcribe` · `POST /api/v1/meta/voice/transcribe` | user | Voice → text (off unless `MUSE_VOICE_ENABLED=true`). |
| `GET /api/v1/meta/spots/nearby` | user | GPS nearby search over real coordinates (Haversine). |
| `/api/v1/admin/*` | admin | Control Center API; admin role re-verified server-side on **every** request. |

Prices in every tool/response are computed server-side in **integer
cents** from `facilities.price_per_hour_cents`.

## Database & money rules

Core tables (`0000_migration.sql`): `profiles`, `user_roles`,
`facilities` (`price_per_hour_cents`, `capacity`, `available`, lat/lng,
features), `wallets` (`available_cents`, `reserved_cents`,
`total_deposited_cents`), `bookings` (status, `access_code`,
`idempotency_key`), `wallet_transactions` (`topup` / `booking_charge` /
`refund`). Admin migration (`0001_admin.sql`) adds `audit_logs`,
`cameras`, `incidents`, `app_settings`, authorised-capacity columns
(`total_capacity` / `authorized_capacity`, `active`) and
`admin_adjust_wallet`. Migration `0002_booking_capacity_guard.sql`
then makes the booking functions enforce that model (see below).

**Money invariants — enforced in SQL, not in the UI:**

- All wallet movement (top-up, booking charge, refund, admin adjustment)
  happens **only** inside `SECURITY DEFINER` functions —
  `demo_topup`, `create_booking`, `cancel_booking`,
  `admin_adjust_wallet` — using `auth.uid()`, row locks (`FOR UPDATE`)
  and idempotency keys. Clients have **read-only** access to
  wallets/transactions, so balances can't be forged or go negative
  (`CHECK (available_cents >= 0)` is the second line of defence).
- Amounts are always **integer cents**; prices come only from
  `facilities.price_per_hour_cents × hours`, computed in the function.
- Booking decrements `facilities.available` in the same transaction;
  cancelling restores it. After migration `0002`, `create_booking`
  also rejects deactivated facilities (`FACILITY_INACTIVE`) and treats
  a facility as full when `LEAST(available, authorized_capacity) < 1`;
  cancellations restore availability only up to authorised capacity
  (`LEAST(authorized_capacity, available + 1)`). The AI assistant can
  never override this — it has no booking tool at all; the database
  makes the final booking/access decision.
- RLS everywhere: users read only their own profile/wallet/bookings/
  transactions; facilities are publicly readable, writable only by
  `admin`/`partner`.

## Internationalisation (EN / AR, RTL)

- Every UI string lives in `src/lib/i18n.tsx` (English + Arabic) and is
  rendered with `t("key")` — **never hardcode user-visible text** in a
  new screen. Add the key in both languages.
- Switching to Arabic sets `dir="rtl"` on the app frame; Tailwind
  logical properties (`ps/pe`, `ms/me`, `start/end`) mirror the layout.
- Money formats as `15.00 MAD` / `15.00 درهم` via `mad(cents, lang)`.

## App shell & scrolling

The app is one fixed-height phone frame (`AppShell.tsx` → `Phone`).
Scrolling is deliberately owned by **one** element:

- `Phone` is `h-dvh` (desktop: `min(860px, 100dvh − 4rem)`, rounded,
  centred) with `overflow-hidden` — the frame itself never scrolls.
- Inside it, the header and the bottom tab bar are in normal flex flow
  (`shrink-0`, always pinned), and `<main class="app-scroll">` is the
  only scroll area: `flex-1 min-h-0 overflow-y-auto` plus the
  `.app-scroll` class in `src/styles.css` (momentum touch scrolling,
  `overscroll-behavior: contain`, thin scrollbar, smooth scrolling).
  `min-h-0` is the load-bearing detail — without it a flex child refuses
  to shrink and the scroll area silently stops scrolling.
- The window/body never scroll inside the app (`overflow-x: clip`,
  `overscroll-behavior-y: none` on `body`). Standalone full-width pages
  (`/admin`) intentionally keep normal document scroll.
- The map screen fills the scroll area exactly (`h-full`) so the page
  doesn't scroll under the map — Leaflet handles its own pan/zoom.
  Horizontal chip/card rails use `.no-scrollbar` (scrollable, no bar).
- If you add a screen: render it inside `<AppShell>`, put normal flow
  content in it, and it scrolls correctly — don't add your own
  `h-screen`/`overflow` wrappers or a second scroll container.

## Meta AI integration — honest status

Verified against Meta's public docs; nothing below is faked. Without
credentials, Muse/SAM/voice report not-configured and the assistant
falls back to grounded mode — the app's own search/booking keep
working either way.

| Feature | Status |
|---|---|
| **Muse Spark assistant** | OpenAI-compatible Chat Completions client with controlled tool calling (tools above). Needs `MODEL_API_KEY` + the exact `MUSE_SPARK_MODEL` from your Meta developer account — Meta has not published a public Muse Spark developer model id, so none is hardcoded or invented. Live calls have **not** been tested from this repo's environment (no Meta credentials available here); the client is covered by mocked-transport tests. |
| **Grounded fallback assistant** | Deterministic, rule-based parking assistant (`app/meta/services/grounded.py` + `src/lib/assistantCore.ts`) over the same real inventory tools. Parses city/feature/price/hours/refund/wallet/“near me” intents in English and Arabic, answers only with real facilities and server-computed prices, and is always labeled (`mode: "grounded_fallback"`, UI badge). It never guesses a location and never claims to be the LLM. |
| **SAM 3.1 vision** | Open weights ([facebookresearch/sam3](https://github.com/facebookresearch/sam3), `facebook/sam3` on Hugging Face) — no Meta-hosted SAM cloud API key exists. Deploy the weights yourself, set `SAM_SERVICE_URL`/`SAM_MODEL`, and the ops camera panel works. SAM only *locates* vehicles/plates; it never reads text and never grants access alone. |
| **EasyOCR plates** | Separate OCR step (optional, `requirements-vision.txt`). Reads below `OCR_MIN_CONFIDENCE` are rejected; access requires a matching real booking in the database. |
| **Muse Voice Transcribe** | `POST /api/v1/voice/transcribe`: multipart `request` JSON (`PUSH_TO_TALK`, language bias Arabic/French/English) + mono 16 kHz WAV (browser WebM/M4A converted with FFmpeg on the backend). Capped at 30 s / 10 MB, never stored or logged. **Off by default.** Darija recognition is not promised — transcripts are shown for editing first. Confirm endpoint/model values in your Meta developer account before going live. |
| **GPS nearby parking** | Explicit-tap foreground geolocation only (never on launch, never tracked/stored), Haversine ranking over real coordinates, 5 km default → 50 km max, distances on cards. |

## Super Admin Control Center

Admins (`admin` role in `user_roles`) get `/admin`, linked from
Operations. The FastAPI backend exposes `/api/v1/admin/*` and
re-verifies the admin role **server-side on every request** using the
caller's own Supabase JWT; the admin RLS policies in
`drizzle/migrations/0001_admin.sql` are the second layer. No
service-role key is configured or used anywhere in this project
(the generated `src/integrations/supabase/client.server.ts` template
file would read one from env, but nothing imports it and the variable
is never set).

**One-time setup:** run `drizzle/migrations/0001_admin.sql` (and then
`0002_booking_capacity_guard.sql`) in the Supabase SQL Editor (see
[Quick start](#2--supabase-database--auth--required)).

Sections: Overview (real counts, bookings-per-day chart, status mix) ·
Users & Accounts (search, suspend/reactivate, grant/revoke roles) ·
Parking Facilities (create/edit, activation toggle) · Bookings (filter,
cancel with the standard refund policy) · Pricing (price edits within
configured bounds, change history) · AI Management (configured/model
visibility, safe reachability health checks, runtime feature toggles) ·
Cameras & Access (camera registry + recent verification events) ·
Payments & Wallet (DEMO — adjustments only through
`admin_adjust_wallet`, never direct balance writes) · Reports
(7/30/90-day summaries + audited CSV export) · Notifications (incident
queue) · Audit Logs (append-only, filterable) · System Settings
(allow-listed keys only — no secrets, no SQL, no shell).

Safety rules enforced server-side: authorised capacity never exceeds
total physical capacity and never drops below active reservations; the
last administrator cannot be suspended or demoted and nobody can suspend
themselves; every sensitive action requires a reason (min 3 chars) and
writes an audit entry in the same transaction as the change. Suspension
blocks the account across the ParkSpot backend immediately; fully
revoking live Supabase sessions would require a service-role key, which
this project deliberately does not use.

## Live demo script (hackathon)

Exact commands, in order. Everything below runs locally with the
seeded data — no Meta credentials needed for steps 1–7.

```sh
# 1. Database: run 0000 → 0001 → 0002 in the Supabase SQL Editor.
# 2. Backend (grounded mode works with zero secrets):
uvicorn app.meta.api:app --port 8000 --host 0.0.0.0
# 3. Frontend (second terminal):
VITE_META_API_URL=http://localhost:8000 npm run dev
```

1. **Health** — open `http://localhost:8000/api/v1/meta/status`:
   JSON flags only (`assistant: "grounded_fallback"` without Meta
   credentials), no secrets.
   Demo accounts (after running `scripts/seed_demo_users.sql`):
   `admin@demo.test` / `Admin123`, `partner@demo.test` / `Partner123`,
   `driver@demo.test` / `Driver123`. Demo-only — delete before real use.
2. **Register** a new driver at `/auth` (any email; auto-confirmed).
3. **Search** on `/home`: filter *Casablanca*; open **Maârif Open
   Lot**. Availability is shown against authorised capacity.
4. **Assistant** (`/assistant`): ask “cheapest parking in Casablanca
   for 3 hours”. The badge shows grounded mode; the answer lists real
   facilities with the server quote `24.00 MAD`. Ask “parking near
   me” — it refuses to guess and points you to **Parking Near Me**.
5. **Book**: book Maârif for 2 h. If the wallet is empty you are sent
   to top up (demo money, clearly labeled). Confirm → you get a text
   **access code**; the facility's `available` count drops by one.
6. **Cancel** the booking from `/bookings` ≥ 2 h before start → 100 %
   refund transaction appears in `/wallet`; availability is restored
   (never above authorised capacity).
7. **Admin** (sign in as `admin@demo.test` after the seed script):
   open `/admin`, deactivate a facility → it disappears from driver
   search and `create_booking` rejects it with `FACILITY_INACTIVE`.
8. **Unauthorized check**: sign in as a normal driver and open
   `/admin` or call `GET /api/v1/admin/overview` → `403`. Call
   `POST /api/v1/meta/assistant/chat` without a token → `401`.
9. **Failure honesty**: stop the backend and reload `/assistant` —
   the app says the backend is not connected instead of inventing
   answers. Voice with `MUSE_VOICE_ENABLED=false` returns
   `not_configured`, not a fake transcript.

Before presenting, run the suites (see [Tests](#tests)) and confirm
they pass on your machine.

## Known limitations

- **Access codes are text only — QR codes are NOT implemented.**
  Bookings show an 8-character code; partners match it against the
  booking (readable under RLS), and the camera pipeline verifies
  plate → real booking automatically. Decision record: a QR that
  encodes the same visible text would add no security, and a secure
  version (HMAC-signed token with expiry + single-use entry marking
  via a new `entered_at` column + a partner verify endpoint) is a
  multi-layer feature that must be tested end-to-end before it ships.
  It is deliberately deferred rather than shipped unverified — the AI
  model and OCR alone must never authorize entry, with or without QR.
- **The wallet is DEMO money.** Top-ups are simulated
  (`demo_topup`); no real payment provider is integrated.
- **Muse Spark has not been live-tested from this repo.** A
  user-supplied model identifier is present in the local backend
  `.env`, but `MODEL_API_KEY` is still the template placeholder, so
  the backend (correctly) reports grounded mode. To go live: put your
  real Meta Model API key in `MODEL_API_KEY` (backend `.env` only),
  confirm the model id is the exact one from your Meta developer
  account, restart the backend, and check
  `GET /api/v1/meta/status` flips `assistant` to `"meta"`. The
  client, tool contracts and failure handling are covered by
  mocked-transport tests. Placeholder values (`REPLACE_ME`,
  `YOUR_PROJECT`) are treated as unset by the backend on purpose.
- **SAM 3.1 is not running anywhere by default.** It is open weights
  you must self-host; `SAM_SERVICE_URL` must be that service's
  http(s) URL (a model id pasted there counts as *not configured*).
  EasyOCR needs the optional heavy `requirements-vision.txt` install.
- **Voice is off by default** and untested live; endpoint/model
  values must be confirmed in your own Meta developer account.
- The FastAPI backend requires migration `0001` (it selects the
  capacity columns); the driver app itself works with `0000` alone.
- Generated Supabase types (`src/integrations/supabase/types.ts`)
  predate migration `0001`, so `authorized_capacity` / `total_capacity`
  / `active` are accessed through narrow TypeScript casts until the
  types are regenerated.

## Tests

```sh
npm test                                     # frontend unit tests (Vitest)
npm run test:watch                           # …in watch mode
pytest tests/ -q                             # all backend tests (mocked — no credentials)
pytest tests/test_meta_integration.py -q     # Meta backend contracts
pytest tests/test_admin.py -q                # admin API: authz, capacity, audit, settings
pytest tests/test_grounded.py -q             # grounded fallback assistant
```

## Build, lint & deployment notes

```sh
npm run build        # production build (Nitro; Cloudflare target by default)
npm run build:dev    # development-mode build
npm run preview      # preview the production build
npm run lint         # ESLint
npm run format       # Prettier (write)
```

Do **not** add Vite plugins manually — `vite.config.ts` uses the Lovable
preset, which already includes TanStack, React, Tailwind, Nitro and the
`@` path alias (see the comment at the top of that file).

## Troubleshooting

| Symptom | Likely cause & fix |
|---|---|
| Blank app / “Missing Supabase environment variable(s)” | `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` not set when the dev server started. Set them and restart Vite (build-time vars). |
| App loads but no facilities | Migration `0000` not run, or run on a different Supabase project than the env vars point to. |
| “Backend not connected” / assistant unavailable | Backend not running or `VITE_META_API_URL` unset/wrong. Start `uvicorn app.meta.api:app --port 8000` and restart the frontend with the var set. With the backend up but no Meta credentials, the assistant answers in labeled grounded mode. Booking/search work without the backend. |
| Admin page shows database errors | Migration `0001_admin.sql` not run yet on this database. The backend needs it too (capacity columns). |
| Bookings ignore authorised capacity / deactivated facility still bookable | Migration `0002_booking_capacity_guard.sql` not run yet. |
| Mic / GPS “unavailable” on a phone | Insecure origin: browsers require HTTPS (or `localhost`) for microphone and geolocation. Use an HTTPS tunnel or deploy. |
| Voice button errors immediately | Voice is off by default: set `MUSE_VOICE_ENABLED=true` + a model API key on the **backend**, and make sure FFmpeg is installed there. |
| Map is grey / tiles missing | Leaflet CSS + OpenStreetMap tiles load from CDNs — check network/CSP. |
| Page doesn't scroll / nav moves with content | You're not inside `<AppShell>`, or a screen added its own `h-screen`/`min-h-screen` wrapper. See [App shell & scrolling](#app-shell--scrolling). |
| Port already in use | Another Vite/uvicorn is running — stop it or pass a different `--port`. |

## Security rules (do not break these)

- Money moves **only** in the `SECURITY DEFINER` SQL functions with
  `auth.uid()`, row locks and idempotency keys; clients are read-only
  on wallets/transactions. Prices are server-computed integer cents.
- No service-role key is configured or used; backend calls use the
  caller's own JWT. Never start using one casually — it bypasses RLS.
- Secrets live only in the backend `.env`; the frontend env is public.
- The AI model may only call the validated tools over real inventory;
  GPS coordinates come only from the user's device, never the model.
- Vision never grants access alone: detection → OCR (confidence-gated)
  → matching real booking, in that order.

## Working with Lovable

This project is connected to [Lovable](https://lovable.dev):

- **Never rewrite published git history** — no force-push, rebase,
  amend or squash of already-pushed commits; it rewrites history on
  Lovable's side and history may be lost.
- Commits pushed to the connected branch sync back to Lovable and show
  up in the editor — keep the branch in a working state.
- You can also build in the [Lovable editor](https://lovable.dev) and
  work locally interchangeably; changes sync both ways through GitHub.

---

*ParkSpot AI — partner parking, authorised capacity, driver-first
navigation. Smarter parking, easier journeys.*
