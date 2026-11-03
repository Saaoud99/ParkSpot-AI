"""Self-hosted SAM 3.1 inference service for ParkSpot camera vision.

Meta ships SAM 3 / 3.1 as open weights (github.com/facebookresearch/sam3,
huggingface.co/facebook/sam3.1). This server loads the official ``sam3``
package and exposes the contract the backend already speaks:

    POST /segment   multipart: image, prompts ("car,vehicle,license plate"), model
                    -> {"detections": [{"label", "score", "box": {"x","y","w","h"}}]}
                       (box coordinates normalised to 0..1)
    GET  /health    {"status": "ok" | "loading" | "error", ...}  (503 while not usable)

Weights are GATED on Hugging Face. One-time setup on this machine:
    1. Sign in at https://huggingface.co/facebook/sam3.1 and accept the license.
    2. Create a read token at https://huggingface.co/settings/tokens
    3. .venv/bin/hf auth login     (paste the token)

Point the backend at it:  SAM_SERVICE_URL=http://localhost:8001  SAM_MODEL=sam3.1
Run:  .venv/bin/python scripts/local_sam_server.py
Env:  SAM_PORT (8001), SAM_VERSION (sam3.1 | sam3), SAM_DEVICE (cpu | mps | cuda),
      SAM_CHECKPOINT (local .pt path, skips the download), SAM_CONFIDENCE (0.5).
Images are processed in memory, never stored or logged. On CPU one frame
takes tens of seconds on an 8 GB laptop; this is a correctness setup, not
a throughput one.
"""
from __future__ import annotations

import asyncio
import importlib.util
import io
import logging
import os
import sys
import threading
import time

# `sam3` imports Triton GPU kernels at module import; on macOS / CPU-only
# machines Triton does not exist. Expose an import-time stub for sam3 only
# (image inference never calls those kernels). torch must finish its own
# "is Triton installed?" probing BEFORE the stub becomes visible, otherwise
# torch's compiler tries to import `triton.backends` from the stub.
import torch  # noqa: E402
import torchvision  # noqa: E402,F401
import torch._dynamo  # noqa: E402,F401
import torch._inductor.runtime.hints  # noqa: E402,F401

if importlib.util.find_spec("triton") is None:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "triton_stub"))


def _install_cpu_device_shim(target: str) -> None:
    """sam3 hardcodes ``device="cuda"`` in a few tensor factories on the image
    path (position cache, decoder coordinate cache). Without a CUDA build of
    torch those calls raise. Remap only that literal to ``target``; every
    other call is untouched."""
    if torch.cuda.is_available():
        return

    def _is_cuda(dev) -> bool:
        return (isinstance(dev, str) and dev.startswith("cuda")) or (
            isinstance(dev, torch.device) and dev.type == "cuda")

    def _wrap(fn):
        def wrapped(*args, **kwargs):
            if _is_cuda(kwargs.get("device")):
                kwargs["device"] = target
            return fn(*args, **kwargs)
        wrapped.__name__ = getattr(fn, "__name__", "factory")
        return wrapped

    for name in ("zeros", "ones", "empty", "full", "arange", "linspace", "tensor", "rand", "randn", "eye"):
        setattr(torch, name, _wrap(getattr(torch, name)))

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

log = logging.getLogger("parkspot.local_sam")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

VERSION = os.environ.get("SAM_VERSION", "sam3.1").strip() or "sam3.1"
DEVICE = os.environ.get("SAM_DEVICE", "cpu").strip() or "cpu"
CHECKPOINT = os.environ.get("SAM_CHECKPOINT", "").strip() or None
CONFIDENCE = float(os.environ.get("SAM_CONFIDENCE", "0.5"))
BPE_URL = "https://raw.githubusercontent.com/facebookresearch/sam3/main/sam3/assets/bpe_simple_vocab_16e6.txt.gz"
CACHE_DIR = os.environ.get("SAM_CACHE_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".local-ai-cache")
GATE_HELP = ("Checkpoint download refused: accept the license at "
             f"https://huggingface.co/facebook/{VERSION} and run `hf auth login` with a read token, "
             "then restart this service.")

app = FastAPI(title="ParkSpot local SAM 3.1 service", version="1.0.0")
_state = {"status": "loading", "detail": "Loading model…", "loaded_at": None}
_model = None
_processor = None
_infer_lock = threading.Lock()


def _load() -> None:
    global _model, _processor
    started = time.perf_counter()
    try:
        from huggingface_hub import hf_hub_download
        from sam3.model_builder import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor

        # The PyPI wheel ships without the CLIP BPE vocabulary the text
        # encoder needs; fetch it once from the official repo.
        bpe_path = os.path.join(CACHE_DIR, "bpe_simple_vocab_16e6.txt.gz")
        if not os.path.exists(bpe_path):
            import urllib.request
            os.makedirs(CACHE_DIR, exist_ok=True)
            log.info("downloading tokenizer vocabulary to %s", bpe_path)
            urllib.request.urlretrieve(BPE_URL, bpe_path)
        ckpt = CHECKPOINT
        if ckpt is None:
            repo_id = "facebook/sam3.1" if VERSION == "sam3.1" else "facebook/sam3"
            ckpt_name = "sam3.1_multiplex.pt" if VERSION == "sam3.1" else "sam3.pt"
            try:
                hf_hub_download(repo_id=repo_id, filename="config.json")
                ckpt = hf_hub_download(repo_id=repo_id, filename=ckpt_name)
            except Exception as e:  # gated repo / no token / offline
                name = e.__class__.__name__
                if any(k in name for k in ("Gated", "Repository", "HfHub", "Auth")) or "401" in str(e) or "403" in str(e):
                    raise RuntimeError(GATE_HELP) from e
                raise
        torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
        _install_cpu_device_shim("cpu" if DEVICE == "cuda" else DEVICE)
        model = build_sam3_image_model(bpe_path=bpe_path, device="cuda" if DEVICE == "cuda" else "cpu",
                                       checkpoint_path=ckpt, load_from_HF=False)
        if DEVICE == "mps":
            model = model.to("mps")
        _processor = Sam3Processor(model, device=DEVICE, confidence_threshold=CONFIDENCE)
        _model = model
        _state.update(status="ok", detail=f"{VERSION} loaded on {DEVICE} in {time.perf_counter() - started:.0f}s",
                      loaded_at=time.time())
        log.info(_state["detail"])
    except Exception as e:
        _state.update(status="error", detail=f"{e.__class__.__name__}: {str(e)[:400]}")
        log.error("model load failed: %s", _state["detail"])


@app.on_event("startup")
async def _start_loading() -> None:
    threading.Thread(target=_load, name="sam-load", daemon=True).start()


@app.get("/")
@app.get("/health")
async def health():
    body = {"service": "local-sam", "model": VERSION, "device": DEVICE, **_state}
    # 503 while loading/broken so the backend probe reports "degraded", not "ok".
    return JSONResponse(status_code=200 if _state["status"] == "ok" else 503, content=body)


def _run(image_bytes: bytes, prompts: list[str]) -> list[dict]:
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    out: list[dict] = []
    with _infer_lock:
        state = _processor.set_image(img)
        for prompt in prompts:
            res = _processor.set_text_prompt(prompt=prompt, state=state)
            boxes = res.get("boxes")
            scores = res.get("scores")
            if boxes is None or scores is None:
                continue
            for (x0, y0, x1, y1), score in zip(boxes.detach().cpu().tolist(), scores.detach().cpu().tolist()):
                out.append({
                    "label": prompt,
                    "score": round(float(score), 4),
                    "box": {"x": max(0.0, x0 / w), "y": max(0.0, y0 / h),
                            "w": max(0.0, (x1 - x0) / w), "h": max(0.0, (y1 - y0) / h)},
                })
    return out


@app.post("/segment")
async def segment(image: UploadFile = File(...), prompts: str = Form(default="car,vehicle,license plate"),
                  model: str | None = Form(default=None)):
    if _state["status"] != "ok":
        return JSONResponse(status_code=503, content={"error": {"message": _state["detail"]}})
    data = await image.read()
    if not data:
        return JSONResponse(status_code=400, content={"error": {"message": "empty image"}})
    labels = [p.strip() for p in prompts.split(",") if p.strip()] or ["object"]
    started = time.perf_counter()
    try:
        detections = await asyncio.to_thread(_run, data, labels)
    except Exception as e:
        log.exception("inference failed")
        return JSONResponse(status_code=500, content={"error": {"message": f"{e.__class__.__name__}"}})
    log.info("segment prompts=%d detections=%d in %.0f ms", len(labels), len(detections),
             (time.perf_counter() - started) * 1000)
    return {"detections": detections, "model": VERSION, "device": DEVICE}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SAM_PORT", "8001")), log_level="info")
