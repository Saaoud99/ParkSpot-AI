from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import async_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from app.workers.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    yield
    stop_scheduler()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline browser hardening for the API and the static shell.

    CSP still needs 'unsafe-inline' for scripts/styles because the Premium
    Light shell uses inline module scripts and Tailwind's CDN runtime; the
    XSS controls therefore live in output encoding (see frontend escaping)
    plus these headers as defence in depth.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=(self)")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://api.mapbox.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://api.mapbox.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https://api.mapbox.com; "
            "connect-src 'self' https://api.mapbox.com https://events.mapbox.com; worker-src 'self' blob:; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        if request.url.path.startswith("/api/"):
            # Auth, availability and booking payloads must never be stored
            # by shared caches or the service worker.
            response.headers.setdefault("Cache-Control", "no-store")
        settings = get_settings()
        if settings.ENV == "prod":
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response


def create_app() -> FastAPI:
    configure_logging()
    s = get_settings()
    app = FastAPI(title=s.APP_NAME, version=s.APP_VERSION, lifespan=lifespan, debug=False)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware, allow_origins=s.CORS_ORIGINS, allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Camera-Key"],
    )
    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict:
        db_ok = "ok"
        try:
            async with async_session_factory() as db:
                await db.execute(text("SELECT 1"))
        except Exception:
            db_ok = "error"
        return {"status": "ok", "version": s.APP_VERSION, "env": s.ENV, "vision_mode": s.VISION_MODE, "db": db_ok}

    app.include_router(v1_router)
    # Static frontend mounted last so API routes win. Anchored to the repo
    # root (not the process cwd) so the UI loads no matter where uvicorn
    # is launched from.
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    return app


app = create_app()
