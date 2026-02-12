"""Assets: signed-url (POST), stream (GET with token). Org-scoped."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, require_csrf, get_asset_for_user
from app.core.security import verify_asset_stream_token
from app.db import get_db, Asset, User
from app.api.schemas import SignedUrlResponse
from app.services.audit import log_audit
from app.services.storage import get_storage
from app.core.metrics import record_signed_url_mint

router = APIRouter(prefix="/assets", tags=["assets"])
settings = get_settings()

# In-memory cache: (asset_id, user_id) -> (url, expires_at). Only when signed_url_cache_ttl_seconds > 0.
_signed_url_cache: dict[tuple[UUID, UUID], tuple[str, datetime]] = {}
_CACHE_BUFFER_SECONDS = 60  # Return cached URL only if it expires more than this in the future


def _get_cached_signed_url(asset_id: UUID, user_id: UUID) -> SignedUrlResponse | None:
    cache_ttl = getattr(settings, "signed_url_cache_ttl_seconds", 0)
    if cache_ttl <= 0:
        return None
    key = (asset_id, user_id)
    entry = _signed_url_cache.get(key)
    if not entry:
        return None
    url, expires_at = entry
    if (expires_at - datetime.now(timezone.utc)).total_seconds() < _CACHE_BUFFER_SECONDS:
        _signed_url_cache.pop(key, None)
        return None
    return SignedUrlResponse(url=url, expires_at=expires_at)


def _set_cached_signed_url(asset_id: UUID, user_id: UUID, url: str, expires_at: datetime) -> None:
    if getattr(settings, "signed_url_cache_ttl_seconds", 0) <= 0:
        return
    _signed_url_cache[(asset_id, user_id)] = (url, expires_at)
    # Simple size cap: drop oldest entries if > 10k
    while len(_signed_url_cache) > 10000:
        _signed_url_cache.pop(next(iter(_signed_url_cache)), None)


@router.post("/{asset_id}/signed-url", response_model=SignedUrlResponse, dependencies=[Depends(require_csrf)])
async def get_signed_url(
    asset_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await get_asset_for_user(asset_id, user, db)
    cached = _get_cached_signed_url(asset_id, user.id)
    if cached:
        return cached
    storage = get_storage()
    ttl = settings.signed_url_ttl_seconds
    if settings.storage_backend == "s3":
        ttl = getattr(settings, "s3_signed_url_ttl_seconds", 300)
    url = storage.create_presigned_get(
        asset.storage_key,
        ttl,
        base_url=str(request.base_url).rstrip("/"),
        asset_id=asset_id,
        org_id=user.org_id,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    _set_cached_signed_url(asset_id, user.id, url, expires_at)
    record_signed_url_mint()
    await log_audit(
        db,
        user.id,
        user.org_id,
        "mint_asset_url",
        event_data={"asset_id": str(asset_id)},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return SignedUrlResponse(url=url, expires_at=expires_at)


@router.get("/{asset_id}/stream")
async def stream_asset(
    asset_id: UUID,
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await get_asset_for_user(asset_id, user, db)
    if not verify_asset_stream_token(token, asset_id, user.org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired token")
    # Dev: serve from backend/dev_assets/{storage_key} (resolve so cwd doesn't matter)
    assets_dir = Path(settings.dev_assets_dir)
    if not assets_dir.is_absolute():
        assets_dir = (Path(__file__).resolve().parent.parent.parent / settings.dev_assets_dir).resolve()
    file_path = assets_dir / asset.storage_key
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(
        file_path,
        media_type=asset.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
        },
    )
