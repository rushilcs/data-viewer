"""Redact sensitive data from structured logs. Never log JWTs, cookies, passwords, invite tokens."""
import re
from typing import Any

# Keys (case-insensitive) that must be redacted in dicts
REDACT_KEYS = frozenset({
    "password", "token", "secret", "authorization", "cookie", "csrf_token",
    "access_token", "refresh_token", "jwt", "api_key", "invite_token",
})


def _redact_key(key: str) -> bool:
    k = key.lower()
    return any(r in k for r in REDACT_KEYS)


def redact_for_log(obj: Any) -> Any:
    """Return a copy of obj safe for logging: sensitive keys replaced with '[REDACTED]'."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if _redact_key(k) else redact_for_log(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return type(obj)(redact_for_log(x) for x in obj)
    if isinstance(obj, str) and _looks_like_secret(obj):
        return "[REDACTED]"
    return obj


def _looks_like_secret(s: str) -> bool:
    """Heuristic: long base64-like or bearer token."""
    if len(s) > 64 and re.match(r"^[A-Za-z0-9_-]+\.([A-Za-z0-9_-]+)\.", s):
        return True  # JWT-like
    if s.lower().startswith("bearer "):
        return True
    return False
