"""Typed errors. Messages never contain credentials or provider payloads."""
from __future__ import annotations


class MetaError(Exception):
    status_code = 502
    code = "provider_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotConfigured(MetaError):
    status_code = 503
    code = "not_configured"


class ProviderTimeout(MetaError):
    status_code = 504
    code = "provider_timeout"


class ProviderUnavailable(MetaError):
    status_code = 502
    code = "provider_unavailable"


class InvalidProviderResponse(MetaError):
    status_code = 502
    code = "invalid_provider_response"


class ValidationFailed(MetaError):
    status_code = 422
    code = "validation_failed"


class Unauthorized(MetaError):
    status_code = 401
    code = "unauthorized"


class Forbidden(MetaError):
    status_code = 403
    code = "forbidden"


class RateLimited(MetaError):
    status_code = 429
    code = "rate_limited"
