"""JWT, password hashing, CSRF token (double-submit cookie)."""
import hashlib
import hmac
import secrets
import time
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from app.core.config import get_settings

settings = get_settings()
_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _ph.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(subject: str, org_id: str) -> str:
    from datetime import datetime, timezone, timedelta
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "org_id": org_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_value: str | None, header_value: str | None) -> bool:
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def create_asset_stream_token(asset_id: UUID, org_id: UUID) -> str:
    """HMAC-signed short-lived token for /api/assets/{id}/stream (dev)."""
    message = f"{asset_id}:{org_id}:{int(time.time())}"
    sig = hmac.new(
        settings.secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{message}:{sig}"


def verify_asset_stream_token(token: str, asset_id: UUID, org_id: UUID) -> bool:
    """Verify token and TTL (e.g. 300s)."""
    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return False
        message, sig = parts
        expected = hmac.new(
            settings.secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        pref, ts = message.rsplit(":", 1)
        if pref != f"{asset_id}:{org_id}":
            return False
        if time.time() - int(ts) > settings.signed_url_ttl_seconds:
            return False
        return True
    except (ValueError, TypeError):
        return False


def create_upload_token(asset_id: UUID, org_id: UUID, dataset_id: UUID, byte_size: int) -> str:
    """HMAC-signed token for PUT /api/ingest/assets/{id}/upload (dev)."""
    ttl = getattr(settings, "upload_token_ttl_seconds", 300)
    expiry_ts = int(time.time()) + ttl
    message = f"{asset_id}:{org_id}:{dataset_id}:{byte_size}:{expiry_ts}"
    sig = hmac.new(
        settings.secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{message}:{sig}"


def verify_upload_token(
    token: str,
    asset_id: UUID,
    org_id: UUID,
    dataset_id: UUID,
    byte_size: int,
) -> bool:
    """Verify upload token and TTL; return True if valid."""
    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return False
        message, sig = parts
        expected = hmac.new(
            settings.secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        # message = asset_id:org_id:dataset_id:byte_size:expiry_ts
        comp = message.split(":")
        if len(comp) != 5:
            return False
        if comp[0] != str(asset_id) or comp[1] != str(org_id) or comp[2] != str(dataset_id):
            return False
        if int(comp[3]) != byte_size:
            return False
        if time.time() > int(comp[4]):
            return False
        return True
    except (ValueError, TypeError):
        return False
