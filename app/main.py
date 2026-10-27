from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

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


def create_app() -> FastAPI:
    configure_logging()
    s = get_settings()
    app = FastAPI(title=s.APP_NAME, version=s.APP_VERSION, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
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
