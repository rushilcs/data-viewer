"""Upload validation: content-type allowlist, max size per kind (docs/05-security.md)."""
import re
from app.core.config import get_settings


def sanitize_storage_filename(filename: str | None) -> str:
    """Safe suffix for storage_key: no path separators, no control chars, bounded length."""
    if not filename or not filename.strip():
        return ""
    # Remove path components and restrict to alphanumeric, dash, underscore, dot
    base = filename.strip().split("/")[-1].split("\\")[-1]
    safe = re.sub(r"[^\w\-.]", "_", base)
    return safe[:200] if len(safe) > 200 else safe

_settings = get_settings()
_ALLOWLIST = set(s.strip() for s in _settings.content_type_allowlist.split(",") if s.strip())
_MB = 1024 * 1024
_LIMITS = {
    "image": _settings.max_byte_size_image_mb * _MB,
    "video": _settings.max_byte_size_video_mb * _MB,
    "audio": _settings.max_byte_size_audio_mb * _MB,
    "other": _settings.max_byte_size_other_mb * _MB,
}


def is_content_type_allowed(content_type: str) -> bool:
    return content_type.strip().lower() in _ALLOWLIST


def max_byte_size_for_kind(kind: str) -> int:
    return _LIMITS.get(kind, _LIMITS["other"])


def validate_file_spec(kind: str, content_type: str, byte_size: int) -> None:
    """Raise ValueError if invalid."""
    if kind not in _LIMITS:
        raise ValueError(f"Invalid kind: {kind}")
    if not is_content_type_allowed(content_type):
        raise ValueError(f"Content type not allowed: {content_type}")
    limit = max_byte_size_for_kind(kind)
    if byte_size <= 0 or byte_size > limit:
        raise ValueError(f"byte_size must be 1..{limit} for kind={kind}")
