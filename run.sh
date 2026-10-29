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
# The server binds 0.0.0.0 so other devices on the same network can reach
# it. On a phone, open the machine's LAN address — NOT 127.0.0.1, which on
# the phone means the phone itself ("127.0.0.1 refused to connect").
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -n "$LAN_IP" ] && echo "On your phone (same Wi-Fi): http://${LAN_IP}:${PORT:-8000}"
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
