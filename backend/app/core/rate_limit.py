"""Simple in-memory rate limit (login, ingest). Dev-friendly; use WAF/API Gateway in prod for scale."""
import time
from collections import defaultdict

from app.core.config import get_settings

settings = get_settings()
_buckets: dict[str, list[float]] = defaultdict(list)
_window = 60.0


def _check_limit(identifier: str, limit_per_minute: int) -> bool:
    now = time.monotonic()
    bucket = _buckets[identifier]
    bucket[:] = [t for t in bucket if now - t < _window]
    if len(bucket) >= limit_per_minute:
        return True
    bucket.append(now)
    return False


def is_login_rate_limited(identifier: str) -> bool:
    return _check_limit(identifier, settings.login_rate_limit_per_minute)


def is_ingest_rate_limited(identifier: str) -> bool:
    """Per-user (or IP) limit for ingest endpoints (create dataset, batch URLs, publish, append)."""
    return _check_limit(identifier, settings.ingest_rate_limit_per_minute)
