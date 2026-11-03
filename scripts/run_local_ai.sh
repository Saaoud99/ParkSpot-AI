#!/usr/bin/env bash
# Start every ParkSpot service on this machine, all free and local:
#   Ollama (chat model behind the Muse Spark contract)  :11434
#   SAM 3.1 segmentation service                        :8001
#   Whisper speech-to-text (Muse Voice contract)        :8002
#   FastAPI backend                                     :8000
#   Vite frontend                                       :8080
# Usage: scripts/run_local_ai.sh          (Ctrl-C stops everything)
# Logs:  .local-ai-logs/*.log
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || { echo "Missing .venv — run: python3.12 -m venv .venv && .venv/bin/pip install -r requirements-meta.txt -r requirements-vision.txt -r requirements-local-ai.txt"; exit 1; }
mkdir -p .local-ai-logs
pids=()
trap 'echo; echo "stopping…"; kill "${pids[@]}" 2>/dev/null || true; wait 2>/dev/null || true' INT TERM EXIT

if ! curl -sf -m 2 http://localhost:11434/api/tags >/dev/null; then
  ollama serve >.local-ai-logs/ollama.log 2>&1 & pids+=($!)
  for _ in $(seq 1 30); do curl -sf -m 1 http://localhost:11434/api/tags >/dev/null && break; sleep 1; done
fi
MODEL="$(grep -E '^MUSE_SPARK_MODEL=' .env | cut -d= -f2- || true)"; MODEL="${MODEL:-llama3.2}"
ollama list 2>/dev/null | grep -q "^${MODEL}" || ollama pull "$MODEL"

$PY scripts/local_sam_server.py >.local-ai-logs/sam.log 2>&1 & pids+=($!)
$PY scripts/local_asr_server.py >.local-ai-logs/asr.log 2>&1 & pids+=($!)
$PY -m uvicorn app.meta.api:app --host 0.0.0.0 --port 8000 >.local-ai-logs/backend.log 2>&1 & pids+=($!)
VITE_META_API_URL=http://localhost:8000 npx vite dev --port 8080 --host >.local-ai-logs/frontend.log 2>&1 & pids+=($!)

echo "backend  http://localhost:8000/healthz"
echo "frontend http://localhost:8080/admin"
echo "sam      http://localhost:8001/health   (503 until the model is loaded)"
echo "asr      http://localhost:8002/health"
echo "logs     .local-ai-logs/"
wait
