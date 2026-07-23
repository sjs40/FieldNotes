"""Small, dependency-free structured logging with deliberate redaction."""
import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from .config import settings

request_context: ContextVar[dict] = ContextVar("request_context", default={})
_SENSITIVE = re.compile(r"(authorization|token|secret|password|credential|database_url|body|email)", re.I)

def safe(value):
    if isinstance(value, str) and len(value) > 16:
        return value[:4] + "…" + value[-4:]
    return value

def log_event(event: str, severity: str = "INFO", **fields) -> None:
    payload = {"timestamp": time.time(), "severity": severity, "environment": "production" if settings.is_production else "development", "event": event, **request_context.get(), **fields}
    payload = {key: ("[redacted]" if _SENSITIVE.search(key) else safe(value)) for key, value in payload.items() if value is not None}
    logging.getLogger("fieldnotes").log(getattr(logging, severity, logging.INFO), json.dumps(payload, default=str))

class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if re.fullmatch(r"[A-Za-z0-9._-]{8,128}", incoming) else str(uuid.uuid4())
        request.state.request_id = request_id
        token = request_context.set({"request_id": request_id, "route": request.url.path, "method": request.method})
        started = time.perf_counter()
        try:
            response = await call_next(request)
            log_event("http_request", duration_ms=round((time.perf_counter()-started)*1000, 2), status_code=response.status_code)
        except Exception as exc:
            log_event("http_request_error", "ERROR", duration_ms=round((time.perf_counter()-started)*1000, 2), error_class=type(exc).__name__, status_code=500)
            raise
        finally:
            request_context.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

def init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.sentry_environment or ("production" if settings.is_production else "development"), traces_sample_rate=settings.sentry_traces_sample_rate, send_default_pii=False)
    except ImportError:
        log_event("sentry_unavailable", "WARNING")
