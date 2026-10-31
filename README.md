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
2. **Whether** — each facility shows real remaining capacity
   (`available / capacity`), updated when bookings are made or cancelled.
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
  invents facilities, prices, permissions or access.
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
| AI / vision backend | FastAPI (Python) in `app/meta/` — Muse Spark tool-calling, SAM 3.1 (self-hosted), EasyOCR, Muse Voice |
| Streaming chat fallback | TanStack server route `src/routes/api/chat.ts` |
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
│   │   └── api/chat.ts        ← streaming chat server route
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
│   │   ├── admin.ts           ← client for /api/v1/admin/*
│   │   ├── auth.tsx           ← Supabase auth provider, roles, error mapping
│   │   └── utils.ts           ← cn() and helpers
│   ├── integrations/supabase/ ← generated Supabase client & auth plumbing
│   ├── styles.css             ← design system (oklch tokens) + .app-scroll / .no-scrollbar
│   ├── router.tsx / server.ts / start.ts
│   └── test/                  ← Vitest setup + routing/auth tests
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
│       ├── sam_vision.py      ← SAM 3.1 client (your self-hosted inference service)
│       ├── easy_ocr.py        ← EasyOCR plate reading (confidence-gated)
│       └── muse_voice.py      ← Muse Voice transcription (FFmpeg → 16 kHz WAV)
│
├── drizzle/migrations/
│   ├── 0000_migration.sql     ← core schema: profiles, roles, facilities, wallets,
│   │                            bookings, transactions + demo_topup/create_booking/cancel_booking
│   └── 0001_admin.sql         ← admin: audit_logs, cameras, incidents, app_settings,
│                                capacity columns, admin_adjust_wallet, admin RLS policies
├── scripts/
│   ├── setup_new_db.sql       ← one-shot setup for a fresh database
│   └── seed_demo_users.sql    ← demo accounts/seed helpers
├── supabase/config.toml       ← local Supabase config
├── tests/
│   ├── test_meta_integration.py ← Meta backend (mocked transports, no credentials needed)
│   └── test_admin.py            ← admin API: authz, capacity, audit, settings
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
- Optional: **FFmpeg** on the backend machine (voice transcription of
  browser WebM/M4A recordings)

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
     facilities (Casablanca ×3, Rabat, Marrakech, Tangier).
   - [`drizzle/migrations/0001_admin.sql`](drizzle/migrations/0001_admin.sql)
     — only needed for `/admin` (audit logs, cameras, incidents,
     settings, capacity columns, admin policies). Until it runs, admin
     endpoints return database errors — that is expected.
   - Optionally [`scripts/seed_demo_users.sql`](scripts/seed_demo_users.sql)
     for demo users.
3. Copy your project URL + publishable key into the frontend env (next
   section). New accounts are auto-confirmed by the seeded
   `handle_new_user` trigger, which also creates their profile, wallet
   and `user` role.

### 3 — Backend (optional, for AI / vision / voice / admin)

The app fully works without it (discovery, booking, wallet). The backend
adds the Muse Spark assistant tools, vision, voice and the admin API.

```sh
pip install -r requirements-meta.txt        # core (light)
pip install -r requirements-vision.txt      # optional EasyOCR (heavy, torch)
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
| `MUSE_SPARK_MODEL` | *(none, intentionally)* | **Exact** chat model id from your Meta developer account. No public id is published by Meta, so none is hardcoded — inventing one would fake the integration. Unset → assistant endpoint returns `not_configured`. |
| `SAM_SERVICE_URL` / `SAM_MODEL` / `SAM_SERVICE_API_KEY` | — | Your self-hosted SAM 3.1 inference service (`POST /segment`). Meta ships SAM as open weights — there is no Meta-hosted SAM API key. |
| `MUSE_VOICE_ENABLED` | `false` | Master switch for voice transcription. |
| `META_VOICE_API_KEY` / `META_VOICE_BASE_URL` / `MUSE_VOICE_MODEL` | `…/v1` / `muse-voice-transcribe-1.0` | Voice endpoint + model (confirm in your Meta account before going live). |
| `MUSE_VOICE_MAX_SECONDS` / `MUSE_VOICE_MAX_UPLOAD_MB` | `30` / `10` | Recording caps. Recordings are converted to mono 16 kHz WAV with FFmpeg, never stored or logged. |
| `NEARBY_SEARCH_DEFAULT_RADIUS_KM` / `NEARBY_SEARCH_MAX_RADIUS_KM` | `5` / `50` | GPS nearby-search radius bounds. |
| `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` | — | Same Supabase project as the frontend; the backend uses it **with the caller's own JWT** (no service-role key exists in this project). |
| `META_TIMEOUT_S` / `META_MAX_RETRIES` / `META_RATE_LIMIT_PER_MINUTE` | `30` / `2` / `30` | Provider timeout, retries, per-user rate limit. |
| `OCR_MIN_CONFIDENCE` | `0.6` | Plate reads below this confidence are rejected. |
| `META_CORS_ORIGINS` | `*` | Comma-separated CORS allow-list. Tighten in production. |

## How to use the app

**As a driver (2 minutes):**

1. Open `/` → splash → onboarding → **Explore** (or sign up).
2. On **Home**, browse facilities, filter by city, or tap
   **Parking Near Me** and allow location.
3. Tap a facility → check price, availability (`available/capacity`) and
   features → **Book this spot**.
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
| `/assistant` | AI assistant chat (Meta backend, streaming fallback) |
| `/auth` | Sign in / sign up / Google OAuth |
| `/profile` | Profile, vehicle plate/model, language, sign out, Operations link |
| `/ops` | Partner operations + SAM/EasyOCR camera panel |
| `/admin` | Super Admin Control Center (full-width, outside the phone frame) |
| `/api/chat` | Server route: streaming chat fallback |

## Backend API

Base: `VITE_META_API_URL` (e.g. `http://localhost:8000`). Every route
verifies the caller's own Supabase JWT; identity never comes from the
request body or the model.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/v1/meta/status` | public | Feature flags only (`assistant`, `voice`, …) — never secrets or model keys. |
| `POST /api/v1/meta/assistant/chat` | user | Muse Spark with controlled tools: `search_facilities`, `get_facility_details`, `check_availability`, `calculate_booking_quote`, `search_nearby_facilities` (device-shared coordinates only — the model can never supply GPS). |
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
`cameras`, `incidents`, `app_settings`, authorised-capacity columns and
`admin_adjust_wallet`.

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
  cancelling restores it (`LEAST(capacity, available + 1)`).
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
credentials the endpoints return `not_configured` and the app's own
search/booking keep working.

| Feature | Status |
|---|---|
| **Muse Spark assistant** | OpenAI-compatible Chat Completions client with controlled tool calling (tools above). Needs `MODEL_API_KEY` + the exact `MUSE_SPARK_MODEL` from your Meta developer account — Meta has not published a public Muse Spark developer model id, so none is hardcoded or invented. |
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
service-role key exists anywhere in this project.

**One-time setup:** run `drizzle/migrations/0001_admin.sql` in the
Supabase SQL Editor (see [Quick start](#2--supabase-database--auth--required)).

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

## Tests

```sh
npm test                                     # frontend unit tests (Vitest)
npm run test:watch                           # …in watch mode
pytest tests/test_meta_integration.py -q     # mocked transports — no credentials needed
pytest tests/test_admin.py -q                # admin API: authz, capacity, audit, settings
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
| “Backend not connected” / assistant unavailable | Backend not running or `VITE_META_API_URL` unset/wrong. Start `uvicorn app.meta.api:app --port 8000` and restart the frontend with the var set. Booking/search still work without it. |
| Admin page shows database errors | Migration `0001_admin.sql` not run yet on this database. |
| Mic / GPS “unavailable” on a phone | Insecure origin: browsers require HTTPS (or `localhost`) for microphone and geolocation. Use an HTTPS tunnel or deploy. |
| Voice button errors immediately | Voice is off by default: set `MUSE_VOICE_ENABLED=true` + a model API key on the **backend**, and make sure FFmpeg is installed there. |
| Map is grey / tiles missing | Leaflet CSS + OpenStreetMap tiles load from CDNs — check network/CSP. |
| Page doesn't scroll / nav moves with content | You're not inside `<AppShell>`, or a screen added its own `h-screen`/`min-h-screen` wrapper. See [App shell & scrolling](#app-shell--scrolling). |
| Port already in use | Another Vite/uvicorn is running — stop it or pass a different `--port`. |

## Security rules (do not break these)

- Money moves **only** in the `SECURITY DEFINER` SQL functions with
  `auth.uid()`, row locks and idempotency keys; clients are read-only
  on wallets/transactions. Prices are server-computed integer cents.
- No service-role key anywhere; backend calls use the caller's own JWT.
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
