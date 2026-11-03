"""Local, free speech-to-text service for ParkSpot voice search.

Muse Voice Transcribe is a Meta-hosted API with no open weights, so it
cannot be self-hosted. This server speaks the *same contract* the backend
already uses (``POST /asr/transcribe`` with a multipart ``request`` JSON +
``audio`` WAV, answering ``{"text": ...}``) but runs the open-source
Whisper model locally through ``faster-whisper`` (CPU, int8).

Point the backend at it:
    META_VOICE_BASE_URL=http://localhost:8002
    META_VOICE_API_KEY=local          # any non-placeholder value
    MUSE_VOICE_MODEL=whisper-small    # shown in the dashboard
    MUSE_VOICE_ENABLED=true

Run:  .venv/bin/python scripts/local_asr_server.py   (port 8002)
Env:  ASR_PORT (8002), ASR_WHISPER_MODEL (small), ASR_DEVICE (cpu),
      ASR_COMPUTE_TYPE (int8). First start downloads the model (~500 MB).
Audio is processed in memory and never written to disk or logged.
"""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
import wave

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

log = logging.getLogger("parkspot.local_asr")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

MODEL_NAME = os.environ.get("ASR_WHISPER_MODEL", "small")
DEVICE = os.environ.get("ASR_DEVICE", "cpu")
COMPUTE = os.environ.get("ASR_COMPUTE_TYPE", "int8")
LANG_CODES = {"arabic": "ar", "french": "fr", "english": "en", "ar": "ar", "fr": "fr", "en": "en"}

app = FastAPI(title="ParkSpot local ASR (faster-whisper)", version="1.0.0")
_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from faster_whisper import WhisperModel  # heavy import, lazy
                log.info("loading whisper model=%s device=%s compute=%s", MODEL_NAME, DEVICE, COMPUTE)
                _model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE)
    return _model


def _decode_wav(data: bytes):
    """mono 16 kHz 16-bit WAV -> float32 numpy array; anything else -> BytesIO."""
    try:
        import numpy as np
        with wave.open(io.BytesIO(data), "rb") as w:
            if w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == 16000 and w.getcomptype() == "NONE":
                pcm = w.readframes(w.getnframes())
                return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        pass
    return io.BytesIO(data)


@app.get("/")
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "local-asr", "model": f"whisper-{MODEL_NAME}", "loaded": _model is not None}


@app.get("/models")
async def models() -> dict:
    """Mirrors the Meta Model API shape so the backend health probe gets a 200."""
    return {"object": "list", "data": [{"id": f"whisper-{MODEL_NAME}", "object": "model", "owned_by": "local"}]}


@app.post("/asr/transcribe")
async def transcribe(request: str = Form(default="{}"), audio: UploadFile = File(...)):
    try:
        req = json.loads(request or "{}")
    except ValueError:
        req = {}
    bias = req.get("languageBias") or []
    language = next((LANG_CODES[str(b).lower()] for b in bias if str(b).lower() in LANG_CODES), None)
    data = await audio.read()
    if not data:
        return JSONResponse(status_code=400, content={"error": {"message": "empty audio"}})
    started = time.perf_counter()
    model = _get_model()
    # The backend always sends mono 16 kHz 16-bit PCM WAV: decode it here
    # with the stdlib instead of PyAV (whose API differs across versions).
    audio_input = _decode_wav(data)
    segments, info = model.transcribe(audio_input, language=language, beam_size=1, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    log.info("transcribed lang=%s chars=%d in %.0f ms", info.language, len(text), (time.perf_counter() - started) * 1000)
    return {"text": text, "language": info.language, "model": f"whisper-{MODEL_NAME}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("ASR_PORT", "8002")), log_level="info")
