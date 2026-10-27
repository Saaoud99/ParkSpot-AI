#!/usr/bin/env bash
# ParkSpot AI — one-command local run (macOS/Linux).
# Usage:  bash run.sh            (then open http://localhost:8000)
#         PORT=8001 bash run.sh  (custom port)
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Creating virtualenv and installing dependencies…"
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
fi

[ -f .env ] || cp .env.example .env

echo "Applying database migrations…"
.venv/bin/python -m alembic upgrade head

echo "Seeding demo data (idempotent)…"
.venv/bin/python -m scripts.seed

echo "Starting ParkSpot AI on http://localhost:${PORT:-8000}  (Ctrl+C to stop)"
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
