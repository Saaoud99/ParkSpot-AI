"""Muse Voice Transcribe — dedicated voice-search service (OFF by default).

Contract implemented (as specified for this project; override every value
via env — META_VOICE_BASE_URL / MUSE_VOICE_MODEL / MODEL_API_KEY):
  POST {META_VOICE_BASE_URL}/asr/transcribe
  Authorization: Bearer <key>
  multipart/form-data:
    request = {"model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV",
               "mode": "PUSH_TO_TALK", "languageBias": ["Arabic","French","English"]}
    audio   = mono 16-bit PCM WAV @ 16 kHz (or 24 kHz)

Browsers record WebM/M4A, not WAV — audio is validated and converted with
FFmpeg (in-memory pipes, nothing written to disk, nothing stored, audio
contents never logged). If FFmpeg is missing and conversion is required,
the request fails honestly instead of sending an unsupported format.
Recording is capped at MUSE_VOICE_MAX_SECONDS (default 30) and
MUSE_VOICE_MAX_UPLOAD_MB (default 10) — far below provider limits.
Darija recognition is NOT promised; transcripts are returned for the user
to review and edit before searching.
"""
from __future__ import annotations

import asyncio
import json
import shutil

import httpx

from ..config import Settings
from ..errors import (InvalidProviderResponse, NotConfigured,
                      ProviderTimeout, ProviderUnavailable, ValidationFailed)

LANGUAGE_BIAS = {"ar": "Arabic", "fr": "French", "en": "English"}
SUPPORTED_LANGUAGES = set(LANGUAGE_BIAS)
INPUT_TYPES = {"audio/webm", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav",
               "audio/ogg", "audio/aac", "audio/x-m4a"}


def _is_wav(data: bytes) -> bool:
    return len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


async def ensure_wav(data: bytes, content_type: str | None, max_seconds: int) -> bytes:
    """Return mono 16 kHz 16-bit WAV bytes, converting with FFmpeg if needed."""
    ctype = (content_type or "").split(";")[0].strip()
    if _is_wav(data):
        return data
    if ctype and ctype not in INPUT_TYPES:
        raise ValidationFailed(f"Unsupported audio type: {ctype}.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ProviderUnavailable(
            "Audio conversion unavailable: FFmpeg is not installed on the backend "
            "and the recording is not WAV. Install FFmpeg or record WAV.")
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, "-v", "error", "-i", "pipe:0",
        "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
        "-t", str(max_seconds), "-f", "wav", "pipe:1",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    try:
        out, _err = await asyncio.wait_for(proc.communicate(data), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        raise ProviderTimeout("Audio conversion timed out.")
    if proc.returncode != 0 or not _is_wav(out):
        raise ValidationFailed("Could not decode the recording. Please try again.")
    return out


class MuseVoiceService:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings
        self._transport = transport

    @property
    def _max_bytes(self) -> int:
        return self._s.muse_voice_max_upload_mb * 1024 * 1024

    def validate_upload(self, data: bytes, content_type: str | None) -> None:
        if not data:
            raise ValidationFailed("Empty recording.")
        if len(data) > self._max_bytes:
            raise ValidationFailed(f"Recording too large (max {self._s.muse_voice_max_upload_mb} MB).")

    async def transcribe(self, audio: bytes, content_type: str = "audio/webm", language: str = "ar") -> dict:
        if not self._s.muse_voice_enabled:
            raise NotConfigured("Voice search is disabled. Set MUSE_VOICE_ENABLED=true and MODEL_API_KEY to enable it.")
        if not self._s.meta_voice_api_key:
            raise NotConfigured("Voice transcription is not configured (MODEL_API_KEY missing).")
        if language not in SUPPORTED_LANGUAGES:
            raise ValidationFailed(f"Unsupported language '{language}'. Supported: ar, fr, en.")
        self.validate_upload(audio, content_type)
        wav = await ensure_wav(audio, content_type, self._s.muse_voice_max_seconds)

        bias = list(dict.fromkeys([LANGUAGE_BIAS[language], "Arabic", "French", "English"]))
        request_json = json.dumps({
            "model": self._s.muse_voice_model,
            "audioEncoding": "WAV",
            "mode": "PUSH_TO_TALK",
            "languageBias": bias,
        })
        headers = {"Authorization": f"Bearer {self._s.meta_voice_api_key}"}
        files = {"audio": ("audio.wav", wav, "audio/wav")}
        form = {"request": request_json}
        last_error: Exception = ProviderUnavailable("Transcription provider unavailable.")
        for attempt in range(self._s.provider_max_retries + 1):
            try:
                async with httpx.AsyncClient(base_url=self._s.meta_voice_base_url, headers=headers,
                                             timeout=self._s.provider_timeout_s, transport=self._transport) as c:
                    r = await c.post("/asr/transcribe", files=files, data=form)
                if r.status_code == 200:
                    payload = r.json() or {}
                    text = payload.get("text") or payload.get("transcript") or ""
                    if not isinstance(text, str) or not text.strip():
                        raise ValidationFailed("No speech recognized. Please try again.")
                    return {"text": text.strip(), "language": language}
                if r.status_code in {401, 403}:
                    raise ProviderUnavailable("Transcription provider rejected the configured credentials.")
                if r.status_code == 429:
                    last_error = ProviderUnavailable("Transcription rate limit reached. Please wait and try again.")
                elif r.status_code >= 500:
                    last_error = ProviderUnavailable(f"Transcription provider error (HTTP {r.status_code}).")
                elif r.status_code == 400:
                    raise ValidationFailed("The recording was rejected as invalid audio.")
                else:
                    raise InvalidProviderResponse(f"Transcription failed (HTTP {r.status_code}).")
            except httpx.TimeoutException:
                last_error = ProviderTimeout("Transcription timed out.")
            except (NotConfigured, ValidationFailed, InvalidProviderResponse, ProviderUnavailable):
                raise
            except httpx.HTTPError:
                last_error = ProviderUnavailable("Transcription provider is unreachable.")
            if attempt < self._s.provider_max_retries:
                await asyncio.sleep(0.4 * (attempt + 1))
        raise last_error  # type: ignore[misc]
