"""ParkSpot Meta AI integration (Muse Spark / SAM 3.1 / EasyOCR / Voice).

This package is the FastAPI backend for Meta-powered features. It is
deliberately separate from the legacy bytecode-only backend under ``app/``
whose sources no longer exist in the repository.

Design rules (non-negotiable):
- All provider credentials live in environment variables, server-side only.
- The LLM never invents facilities, prices, permissions, or access decisions.
  It may only call the validated tools in :mod:`app.meta.tools`, which read
  real inventory through :mod:`app.meta.inventory`.
- Every provider is disabled-by-default: without credentials the endpoints
  return an honest ``not_configured`` error, never a fabricated answer.
"""
