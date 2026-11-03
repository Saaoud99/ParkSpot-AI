# Running the AI services locally on Ubuntu

This guide sets up every AI module of ParkSpot AI on one Ubuntu machine,
with no paid API keys:

| Dashboard module | What runs locally | Port |
|---|---|---|
| Muse Spark (assistant) | [Ollama](https://ollama.com) serving Meta **Llama 3.2** through its OpenAI-compatible API | 11434 |
| Muse Voice Transcribe | open-source **Whisper** via `faster-whisper` (`scripts/local_asr_server.py`) | 8002 |
| SAM 3.1 (camera vision) | the official **`sam3`** package with Meta's SAM 3.1 weights (`scripts/local_sam_server.py`) | 8001 |
| EasyOCR (plate reading) | **EasyOCR** inside the backend process | — |
| FastAPI backend | `app.meta.api` | 8000 |
| Web app | Vite dev server | 8080 |

Two honest notes before you start:

- **Muse Spark and Muse Voice Transcribe are hosted Meta APIs.** They have
  no open weights, so they cannot be self-hosted. The backend speaks their
  request contracts, and locally those contracts are served by Llama 3.2
  and Whisper. The admin dashboard always shows the real model id that is
  configured (`llama3.2`, `whisper-small`), never a Muse label.
- **SAM 3.1 and EasyOCR are genuinely the real models.** SAM 3.1 weights
  are gated on Hugging Face: you must accept Meta's license once (free).

Tested on Ubuntu 22.04 and 24.04, x86_64. An NVIDIA GPU is optional; on
CPU, SAM 3.1 takes tens of seconds per camera frame, everything else is
quick.

---

## 1. System packages

```bash
sudo apt-get update
sudo apt-get install -y git curl ffmpeg build-essential python3-venv python3-dev
```

The backend needs **Python 3.12 or newer** (`sam3` requires it).

- Ubuntu 24.04 ships Python 3.12: `sudo apt-get install -y python3.12-venv`
- Ubuntu 22.04 ships 3.10. Add the deadsnakes PPA:

  ```bash
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update
  sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
  ```

Node.js 20+ is needed for the web app (Node 22 recommended):

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

## 2. Ollama + Llama 3.2 (assistant)

```bash
curl -fsSL https://ollama.com/install.sh | sh     # installs and enables a systemd service
ollama pull llama3.2                               # ~2 GB, Llama 3.2 3B with tool calling
curl -s http://localhost:11434/v1/models           # should list llama3.2
```

With 16 GB RAM or more, `ollama pull llama3.1:8b` gives noticeably better
tool use; set `MUSE_SPARK_MODEL=llama3.1:8b` in `.env` if you use it.

## 3. Python environment

```bash
git clone <your fork url> parkspot-ai && cd parkspot-ai
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-meta.txt -r requirements-vision.txt -r requirements-local-ai.txt
```

`requirements-vision.txt` pulls in PyTorch and EasyOCR, `requirements-local-ai.txt`
adds `sam3` and `faster-whisper`. pip prints one harmless warning: `sam3`
pins `typing_extensions<4.16` while pydantic needs a newer one; the newer
one is kept and works.

**NVIDIA GPU (optional).** Install the CUDA build of PyTorch *before* the
requirements above so the others reuse it:

```bash
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

Then set `SAM_DEVICE=cuda` when starting the SAM server (section 5).

## 4. SAM 3.1 weights (one-time, free)

1. Sign in to Hugging Face and accept the license at
   <https://huggingface.co/facebook/sam3.1>.
2. Create a **read** token at <https://huggingface.co/settings/tokens>.
3. Log in once on the machine:

   ```bash
   .venv/bin/hf auth login
   ```

The checkpoint (~3 GB) downloads automatically the first time the SAM
server starts. Until the license is accepted the server stays up but
answers `503` with the exact fix in its `detail` field, and the admin
dashboard shows the module as *degraded*.

## 5. Configuration

Create `.env` in the project root (it is git-ignored). Minimal local
setup:

```ini
# Supabase project (auth + inventory) — same values as the web app
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<publishable key>
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<publishable key>
VITE_META_API_URL=http://localhost:8000

# Assistant → local Ollama (OpenAI-compatible endpoint)
MODEL_API_KEY=ollama
META_BASE_URL=http://localhost:11434/v1
MUSE_SPARK_MODEL=llama3.2

# Camera vision → local SAM 3.1 service
SAM_SERVICE_URL=http://localhost:8001
SAM_MODEL=sam3.1

# Voice → local Whisper service
MUSE_VOICE_ENABLED=true
META_VOICE_API_KEY=local
META_VOICE_BASE_URL=http://localhost:8002
MUSE_VOICE_MODEL=whisper-small
```

All other variables keep their defaults (see the main README's
environment table). Useful extras:

| Variable | Default | Purpose |
|---|---|---|
| `SAM_DEVICE` | `cpu` | `cuda` on an NVIDIA machine |
| `SAM_VERSION` | `sam3.1` | `sam3` to use the first-generation checkpoint |
| `SAM_CHECKPOINT` | — | path to a local `.pt` to skip the download |
| `ASR_WHISPER_MODEL` | `small` | `base` is faster, `medium` more accurate |
| `ASR_DEVICE` / `ASR_COMPUTE_TYPE` | `cpu` / `int8` | `cuda` / `float16` on a GPU |
| `AI_FLAGS_STATE_PATH` | `.ai_flags.json` | where the dashboard's module switches persist |

## 6. Start everything

```bash
npm install
scripts/run_local_ai.sh
```

The launcher starts Ollama if it is not already running, pulls the model
if missing, then starts the SAM server, the Whisper server, the FastAPI
backend and the web app. Logs go to `.local-ai-logs/`. `Ctrl-C` stops all
of them.

To run the pieces by hand instead:

```bash
.venv/bin/python scripts/local_sam_server.py                       # :8001
.venv/bin/python scripts/local_asr_server.py                       # :8002
.venv/bin/python -m uvicorn app.meta.api:app --host 0.0.0.0 --port 8000
VITE_META_API_URL=http://localhost:8000 npx vite dev --port 8080 --host
```

## 7. Verify

```bash
curl -s http://localhost:8000/healthz                 # backend liveness: instance id, uptime
curl -s http://localhost:8000/api/v1/meta/status      # assistant: "meta", voice: "enabled", vision_sam: "configured"
curl -s http://localhost:8002/health                  # whisper
curl -s http://localhost:8001/health                  # sam: "ok" once the weights are loaded
```

Then open <http://localhost:8080/admin> as an admin and use **Check all**
on the AI Management page. Expected result: Muse Spark, Muse Voice
Transcribe and EasyOCR *OK*; SAM 3.1 *OK* after its weights are loaded.

Quick functional checks:

```bash
# Whisper: speak a short WAV (mono 16 kHz) and read the transcript
curl -s -F 'request={"model":"whisper-small","audioEncoding":"WAV","mode":"PUSH_TO_TALK","languageBias":["Arabic","French","English"]}' \
     -F "audio=@sample.wav;type=audio/wav" http://localhost:8002/asr/transcribe

# SAM 3.1: boxes for cars and plates in a frame
curl -s -F "image=@frame.jpg" -F "prompts=car,vehicle,license plate" http://localhost:8001/segment
```

## 8. Keep the services running (optional systemd units)

Example for the SAM server; copy for the Whisper server and the backend
with the matching command lines from section 6.

```ini
# /etc/systemd/system/parkspot-sam.service
[Unit]
Description=ParkSpot local SAM 3.1 service
After=network.target

[Service]
User=<your user>
WorkingDirectory=/home/<your user>/parkspot-ai
Environment=SAM_DEVICE=cpu
ExecStart=/home/<your user>/parkspot-ai/.venv/bin/python scripts/local_sam_server.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now parkspot-sam
```

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ollama pull` or chat fails with `llama-server binary not found` | A broken Ollama package. Re-run the official install script from section 2. |
| Backend log: `facilities table lacks the 0001_admin.sql columns` | Supabase migrations 0001–0003 not applied yet. The assistant still works (legacy column set); run the migrations in the Supabase SQL editor to enable the admin pages and the booking capacity guard. |
| SAM `/health` says *Checkpoint download refused* | License not accepted or no token: section 4. |
| SAM `/health` says *loading* for minutes | Normal on first start (3 GB download, then model build). On CPU allow a few minutes. |
| `ModuleNotFoundError: triton` when starting SAM on a machine without CUDA | Handled automatically: the server loads a small import-time stub from `scripts/triton_stub/`. Make sure you start it from the project root. |
| Whisper transcribes nothing | The recording was silent or shorter than a second. Browser recordings are converted with FFmpeg on the backend; confirm `ffmpeg -version` works. |
| Dashboard says *Backend unreachable* | `VITE_META_API_URL` missing when the web app was started, or the backend is down (`curl localhost:8000/healthz`). |
| Chat answers "no matching parking" for a city | Correct behaviour when the database has no bookable facility there (zero free spaces or none seeded). |

## 10. Switching back to Meta's hosted APIs

If you obtain Meta Model API access later, only `.env` changes:

```ini
MODEL_API_KEY=<your Meta key>
META_BASE_URL=https://api.meta.ai/v1
MUSE_SPARK_MODEL=muse-spark-1.3
META_VOICE_API_KEY=<your Meta key>
META_VOICE_BASE_URL=https://api.meta.ai/v1
MUSE_VOICE_MODEL=muse-voice-transcribe-1.0
```

SAM 3.1 and EasyOCR stay local either way.
