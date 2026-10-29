from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, detail: str, *, code: str | None = None, status_code: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code})

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo submitted values back: pydantic's default errors include
        # the raw `input`, which for auth forms would reflect passwords.
        safe = [{"loc": [str(p) for p in e.get("loc", ())], "msg": e.get("msg", "invalid value"), "type": e.get("type", "value_error")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": safe, "code": "validation_error"})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(status_code=500, content={"detail": "internal error", "code": "internal_error"})
