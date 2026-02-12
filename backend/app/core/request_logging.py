"""Structured request logging: request_id, route, status, latency. Optional org_id/user_id from state."""
import json
import logging
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings
from app.core.logging_redaction import redact_for_log

logger = logging.getLogger("app.request")


def _safe_extra(request: Request, status_code: int, latency_ms: float) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "request_id": getattr(request.state, "request_id", None),
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "latency_ms": round(latency_ms, 2),
    }
    if hasattr(request.state, "org_id") and request.state.org_id is not None:
        extra["org_id"] = str(request.state.org_id)
    if hasattr(request.state, "user_id") and request.state.user_id is not None:
        extra["user_id"] = str(request.state.user_id)
    return redact_for_log(extra)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assign request_id and log one structured line per request (route, status, latency)."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000
        extra = _safe_extra(request, response.status_code, latency_ms)
        # Single JSON line when log_json; else standard log with extra
        if get_settings().log_json:
            logger.info(json.dumps({"event": "request", **extra}))
        else:
            logger.info("request %s %s %s %.2fms", request.method, request.url.path, response.status_code, latency_ms, extra=extra)
        response.headers["X-Request-ID"] = request_id
        # Prometheus metrics (skip /metrics and health to avoid noise)
        if request.url.path not in ("/metrics", "/health", "/healthz", "/readyz"):
            try:
                from app.core.metrics import record_request
                record_request(request.method, request.url.path, response.status_code, latency_ms / 1000.0)
            except Exception:
                pass
        return response
